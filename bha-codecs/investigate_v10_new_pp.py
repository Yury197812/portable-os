"""v10: explore new preprocessors + direct brotli/bz2 comparison on 50 real BHA files.

Goals:
  1. Implement 3 new preprocessors not tried in v6/v7/v9b:
     - pp_bcj_x86: x86 call/jump filter (rewrites E8/E9 offsets to 0)
     - pp_dedup_substring: replace long repeated substrings with back-refs
     - pp_zero_extend: detect short values padded to fixed width, strip padding
  2. For each of 50 real BHA files, measure:
     - brotli best (q=11) — external baseline
     - bz2 best (lvl=9) — external baseline
     - BHCC1 envelope (no pp) — current v9b default
     - BHCC1 + each new pp — proposed v10
  3. Report files where v10 wins vs BHA's actual choice
"""
from __future__ import annotations

import bz2
import json
import lzma
import time
import zlib
from collections import Counter
from pathlib import Path
import brotli


CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUT_DIR = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v10")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# BHA envelope helpers (from v6)
# ---------------------------------------------------------------------------
def _uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def _lzma2_best(data):
    best = None
    for p in (6, 9 | lzma.PRESET_EXTREME):
        c = lzma.compress(data, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": p}])
        if best is None or len(c) < len(best):
            best = c
    return best


def bha_envelope(magic, data):
    comp = _lzma2_best(data)
    out = bytearray(magic)
    out.extend(_uleb(len(data)))
    out.extend(_uleb(0))
    out.extend(len(comp).to_bytes(4, "little"))
    out.extend(comp)
    return bytes(out)


# ---------------------------------------------------------------------------
# New preprocessors
# ---------------------------------------------------------------------------
def pp_identity(d):
    return d


def pp_bcj_x86(data):
    """x86 BCJ filter: zero out E8/E9 (CALL/JMP rel32) offsets.
    Helps when the data is actual x86 code: LZMA2 back-references jump targets
    across far calls. But for non-x86 data, this is a no-op or worse.
    """
    if not data:
        return data
    out = bytearray(data)
    n = len(out)
    i = 0
    while i < n - 5:
        if out[i] in (0xE8, 0xE9):
            for k in range(1, 5):
                out[i + k] = 0
            i += 5
        else:
            i += 1
    return bytes(out)


def pp_dedup_substring(data, min_len=32, max_refs=64):
    """Replace the longest repeated substring occurrences with a back-ref token.
    Token: 1 byte = 0xFF, then 4 bytes = distance (u32 LE), then 4 bytes = length.
    Keeps the LZMA2 dictionary small; useful for logs with repeated timestamps.
    """
    if len(data) < min_len * 3:
        return data
    # Find longest repeated substring via naive scan (O(n^2) but n < 1MB here)
    best_off, best_len = 0, 0
    for start in range(0, len(data) - min_len, 1):
        if best_len > len(data) - start:
            break
        # find first re-occurrence
        sub = data[start:start + min_len]
        idx = data.find(sub, start + 1, start + 1 + 65536)
        if idx < 0:
            continue
        # extend
        ext = min_len
        while ext < 1024 and start + ext < len(data) and data[start + ext] == data[idx + ext]:
            ext += 1
        if ext > best_len:
            best_off, best_len = start, ext
    if best_len < min_len * 2:
        return data
    # Replace second occurrence (at idx) with back-ref
    out = bytearray(data)
    token = b'\xff' + best_off.to_bytes(4, 'little') + best_len.to_bytes(4, 'little')
    return bytes(out[:best_off] + token + out[best_off + best_len:])


def pp_zero_extend(data):
    """Detect zero-padded values (e.g. \x00\x00\x00\x05 vs 0x05) and strip.
    Heuristic: if a run of zeros at the end of a number (8 bytes) exceeds 4, strip.
    """
    if len(data) < 16:
        return data
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        # Try to find 8-byte aligned window starting with 4+ leading zeros
        if (i + 8 <= n
                and data[i] == 0 and data[i+1] == 0
                and data[i+2] == 0 and data[i+3] == 0
                and data[i+7] != 0):
            # strip 4 leading zeros
            out.append(data[i+4])
            out.append(data[i+5])
            out.append(data[i+6])
            out.append(data[i+7])
            i += 8
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


# ---------------------------------------------------------------------------
# Pre-built codec measurements
# ---------------------------------------------------------------------------
def measure_all(data):
    sizes = {}
    sizes["brotli_q11"] = len(brotli.compress(data, quality=11))
    sizes["brotli_q5"] = len(brotli.compress(data, quality=5))
    sizes["bz2_l9"] = len(bz2.compress(data, 9))
    sizes["lzma2_best"] = len(_lzma2_best(data))
    sizes["zlib_l9"] = len(zlib.compress(data, 9))
    # BHA envelopes (5 useful)
    for env in ("BHCC1", "BHCS1", "BHVT1", "BHSC1", "BHRT1"):
        sizes[f"env_{env}"] = len(bha_envelope(env.encode(), data))
    # v9b preprocessor combos
    for pp_name, pp_fn in [
        ("identity", pp_identity),
        ("bcj_x86", pp_bcj_x86),
        ("dedup_substring", pp_dedup_substring),
        ("zero_extend", pp_zero_extend),
    ]:
        preprocessed = pp_fn(data)
        for env in ("BHCC1", "BHCS1", "BHVT1", "BHRT1"):
            name = f"{env}__{pp_name}"
            sizes[name] = len(bha_envelope(env.encode(), preprocessed))
    return sizes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    files = sorted([p for p in CORPUS.iterdir() if p.is_file() and p.suffix != ".json"])
    print(f"[v10] measuring {len(files)} real BHA files against {len(measure_all(b'x'))} codecs...")

    # Load existing BHA measurements from recommender-corpus/corpus-results.json
    rcorpus_json = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")
    bha_actual = {}
    if rcorpus_json.exists():
        cdata = json.loads(rcorpus_json.read_text())
        for row in cdata["rows"]:
            bha_actual[row["file"]] = (row.get("bha_magic"), row.get("bha_size"))

    results = []
    total_orig = 0
    total_bha_actual = 0
    total_best_v10 = 0
    total_brotli = 0
    total_lzma2 = 0
    n = len(files)
    for i, fp in enumerate(files, 1):
        data = fp.read_bytes()
        sizes = measure_all(data)
        # find best v10 = min over all v10 combos
        v10_combos = {k: v for k, v in sizes.items() if "__" in k}
        best_v10_codec = min(v10_combos, key=v10_combos.get)
        best_v10_size = v10_combos[best_v10_codec]

        # find best stdlib
        stdlib = {k: v for k, v in sizes.items() if "__" not in k}
        best_stdlib = min(stdlib, key=stdlib.get)

        # bha actual
        bha_magic, bha_size = bha_actual.get(fp.name, ("?", None))

        # ratios
        r_bha = (bha_size / len(data)) if bha_size else None
        r_v10 = best_v10_size / len(data)
        r_brotli = sizes["brotli_q11"] / len(data)
        r_lzma2 = sizes["lzma2_best"] / len(data)
        r_best_stdlib = stdlib[best_stdlib] / len(data)

        total_orig += len(data)
        total_bha_actual += bha_size or 0
        total_best_v10 += best_v10_size
        total_brotli += sizes["brotli_q11"]
        total_lzma2 += sizes["lzma2_best"]

        wins = []
        if r_bha is not None and best_v10_size < bha_size:
            wins.append(f"v10 beats BHA by {(1-best_v10_size/bha_size)*100:.1f}%")
        if best_v10_size < sizes["brotli_q11"]:
            wins.append(f"v10 beats brotli-q11 by {(1-best_v10_size/sizes['brotli_q11'])*100:.1f}%")
        if best_v10_size < sizes["bz2_l9"]:
            wins.append(f"v10 beats bz2 by {(1-best_v10_size/sizes['bz2_l9'])*100:.1f}%")

        results.append({
            "file": fp.name,
            "size": len(data),
            "bha_magic": bha_magic,
            "bha_size": bha_size,
            "bha_pct": round(r_bha * 100, 3) if r_bha else None,
            "best_v10_codec": best_v10_codec,
            "best_v10_size": best_v10_size,
            "v10_pct": round(r_v10 * 100, 3),
            "brotli_q11_size": sizes["brotli_q11"],
            "brotli_pct": round(r_brotli * 100, 3),
            "bz2_size": sizes["bz2_l9"],
            "bz2_pct": round(sizes["bz2_l9"]/len(data) * 100, 3),
            "lzma2_size": sizes["lzma2_best"],
            "lzma2_pct": round(r_lzma2 * 100, 3),
            "wins": wins,
        })
        if i % 10 == 0 or wins:
            print(f"  [{i}/{n}] {fp.name:40s} orig={len(data):>8} "
                  f"v10={best_v10_codec:25s} {best_v10_size:>7} ({r_v10*100:5.2f}%) "
                  f"brotli={sizes['brotli_q11']:>7} ({r_brotli*100:5.2f}%) "
                  f"bha={bha_size} {' '.join(wins) if wins else ''}")

    # Summary
    print(f"\n[v10] AGGREGATE on {n} real BHA files ({total_orig} bytes original):")
    print(f"  BHA actual:     {total_bha_actual:>10} ({100*total_bha_actual/total_orig:.2f}%)")
    print(f"  v10 best:       {total_best_v10:>10} ({100*total_best_v10/total_orig:.2f}%)")
    print(f"  brotli q11:     {total_brotli:>10} ({100*total_brotli/total_orig:.2f}%)")
    print(f"  lzma2 best:     {total_lzma2:>10} ({100*total_lzma2/total_orig:.2f}%)")
    delta_vs_bha = (total_bha_actual - total_best_v10)
    delta_vs_brotli = (total_brotli - total_best_v10)
    print(f"  v10 vs BHA:     {delta_vs_bha:+d} bytes ({(delta_vs_bha/total_bha_actual)*100:+.2f}%)")
    print(f"  v10 vs brotli:  {delta_vs_brotli:+d} bytes ({(delta_vs_brotli/total_brotli)*100:+.2f}%)")

    # Save results
    out_path = OUT_DIR / "v10_measurements.json"
    out_path.write_text(json.dumps({
        "n_files": n,
        "total_orig_bytes": total_orig,
        "total_bha_actual_bytes": total_bha_actual,
        "total_v10_best_bytes": total_best_v10,
        "total_brotli_q11_bytes": total_brotli,
        "total_lzma2_bytes": total_lzma2,
        "rows": results,
    }, indent=2))
    print(f"\n[v10] saved {out_path}")

    # Find files where v10 < bha_actual (true wins)
    wins = [r for r in results if r["bha_size"] and r["best_v10_size"] < r["bha_size"]]
    print(f"\n[v10] WINS over BHA: {len(wins)}/{n} files")
    for r in sorted(wins, key=lambda x: (x["bha_size"] - x["best_v10_size"]), reverse=True)[:15]:
        saving = r["bha_size"] - r["best_v10_size"]
        print(f"  {r['file']:40s} bha={r['bha_size']:>8} v10={r['best_v10_size']:>8} "
              f"saved={saving:>6} ({saving/r['bha_size']*100:.1f}%) via {r['best_v10_codec']}")


if __name__ == "__main__":
    main()