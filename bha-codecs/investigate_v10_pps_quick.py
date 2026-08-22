"""Quick v10 preprocessor evaluation — only BHA envelopes, skip brotli/bz2.

Goal: see if pp_bcj_x86 / pp_dedup_substring / pp_zero_extend help on the
50-file BHA corpus when combined with existing BHA envelopes.
"""
import sys, time, json, lzma
from pathlib import Path

sys.path.insert(0, r'D:\4\bha-codecs')
from investigate_v10_new_pp import (
    pp_identity, pp_bcj_x86, pp_dedup_substring, pp_zero_extend,
    bha_envelope, _uleb,
)


def _lzma2_fast(data):
    """Fast LZMA2 — preset 6 only.

    The EXTREME preset gives ~1-2% extra size but takes 5-10x longer.
    For preprocessor screening, preset 6 is sufficient to detect wins.
    """
    import lzma
    return lzma.compress(data, format=lzma.FORMAT_RAW,
                         filters=[{"id": lzma.FILTER_LZMA2, "preset": 6}])


def bha_envelope_fast(magic, data):
    """Same envelope as bha_envelope but with preset 6 (fast)."""
    comp = _lzma2_fast(data)
    out = bytearray(magic)
    out.extend(_uleb(len(data)))
    out.extend(_uleb(0))
    out.extend(len(comp).to_bytes(4, "little"))
    out.extend(comp)
    return bytes(out)


CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
RCORPUS = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")
OUT_DIR = Path(r"D:\4\bha-codecs\benchmark\v10-pp-quick")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Preprocessors to test
PP_LIST = [
    ("identity", pp_identity),
    ("bcj_x86", pp_bcj_x86),
    ("dedup_substring", pp_dedup_substring),
    ("zero_extend", pp_zero_extend),
]
ENVELOPES = ["BHCC1", "BHCS1", "BHVT1", "BHRT1"]


def measure_file(data):
    """Returns dict of {pp_name}__{env} -> encoded_size."""
    sizes = {}
    for pp_name, pp_fn in PP_LIST:
        try:
            preprocessed = pp_fn(data)
        except Exception:
            for env in ENVELOPES:
                sizes[f"{env}__{pp_name}"] = 10**9  # huge so it never wins
            continue
        for env in ENVELOPES:
            arc = bha_envelope_fast(env.encode(), preprocessed)
            sizes[f"{env}__{pp_name}"] = len(arc)
    return sizes


def main():
    # Skip files >2MB to keep wall clock reasonable — the LZMA2 step
    # on a 5MB file with 16 codecs can take minutes.
    all_files = sorted([p for p in CORPUS.iterdir() if p.is_file() and p.suffix != ".json"])
    files = [p for p in all_files if p.stat().st_size <= 2 * 1024 * 1024]
    skipped = [p for p in all_files if p not in files]
    n = len(files)
    print(f"[quick-v10] measuring {n} files (skipped {len(skipped)} >2MB: {[p.name for p in skipped]})")

    # BHA ground truth
    bha_actual = {}
    if RCORPUS.exists():
        cdata = json.loads(RCORPUS.read_text())
        for row in cdata["rows"]:
            bha_actual[row["file"]] = (row.get("bha_magic"), row.get("bha_size"))

    results = []
    total_orig = total_bha = total_v10 = 0
    wins_over_bha = []
    t_total = time.perf_counter()

    for i, fp in enumerate(files, 1):
        t0 = time.perf_counter()
        data = fp.read_bytes()
        sizes = measure_file(data)
        t = time.perf_counter() - t0
        # Best v10 codec
        best_codec = min(sizes, key=sizes.get)
        best_size = sizes[best_codec]

        bha_magic, bha_size = bha_actual.get(fp.name, ("?", None))
        delta = (bha_size - best_size) if bha_size else 0
        win = bha_size and best_size < bha_size
        if win:
            wins_over_bha.append({
                "file": fp.name,
                "bha_magic": bha_magic,
                "bha_size": bha_size,
                "v10_codec": best_codec,
                "v10_size": best_size,
                "saved": delta,
                "saved_pct": round(delta / bha_size * 100, 2),
            })

        results.append({
            "file": fp.name,
            "size": len(data),
            "bha_magic": bha_magic,
            "bha_size": bha_size,
            "v10_best": best_codec,
            "v10_size": best_size,
            "delta_vs_bha": delta,
            "win": bool(win),
            "all_sizes": sizes,
            "measure_ms": round(t * 1000, 1),
        })
        total_orig += len(data)
        if bha_size: total_bha += bha_size
        total_v10 += best_size
        # Progress every 10 files
        if i % 10 == 0 or win:
            win_marker = " WIN" if win else ""
            print(f"  [{i}/{n}] {fp.name[:35]:35s} {len(data):>8d} -> {best_size:>7d} ({best_codec:25s}){win_marker}", flush=True)

    elapsed = time.perf_counter() - t_total
    print(f"\n[quick-v10] total elapsed: {elapsed:.1f}s")
    print(f"[quick-v10] aggregate on {n} files ({total_orig} bytes):")
    print(f"  BHA actual:   {total_bha:>10} ({100*total_bha/total_orig:.2f}%)")
    print(f"  v10 best:     {total_v10:>10} ({100*total_v10/total_orig:.2f}%)")
    if total_bha:
        delta_bha = total_bha - total_v10
        print(f"  delta vs BHA: {delta_bha:+d} bytes ({delta_bha/total_bha*100:+.2f}%)")
    print(f"  wins over BHA: {len(wins_over_bha)}/{n}")

    if wins_over_bha:
        print("\n[quick-v10] top wins over BHA:")
        for w in sorted(wins_over_bha, key=lambda x: -x["saved"])[:15]:
            print(f"  {w['file']:40s} bha={w['bha_size']:>8d} ({w['bha_magic']:>5s}) "
                  f"v10={w['v10_size']:>8d} saved={w['saved']:+d} ({w['saved_pct']:+.1f}%) via {w['v10_codec']}")

    # Save
    out_path = OUT_DIR / "quick_v10_results.json"
    out_path.write_text(json.dumps({
        "n_files": n,
        "elapsed_s": round(elapsed, 2),
        "total_orig": total_orig,
        "total_bha": total_bha,
        "total_v10": total_v10,
        "delta_vs_bha_bytes": (total_bha - total_v10) if total_bha else 0,
        "wins_count": len(wins_over_bha),
        "wins_top15": sorted(wins_over_bha, key=lambda x: -x["saved"])[:15],
        "rows": results,
    }, indent=2))
    print(f"\n[quick-v10] saved {out_path}")


if __name__ == "__main__":
    main()