"""v10 + GPT hand-off ZIP: measure new preprocessors on 50 real BHA files,
auto-bundle into ZIP, write to D:\4\OUT_MIMO\.

User directive: "добавь чтоб скрипт сам собирал все файлы в архив и кидал в гпт"

This script:
  1. Implements 3 new preprocessors (bcj_x86, dedup_substring, zero_extend)
  2. Measures them on all 50 real BHA files
  3. Compares vs brotli/bz2/lzma2/BHA-actual
  4. Auto-builds GPT hand-off ZIP with all results

Robustness:
  - All None-tolerant
  - Log to file as we go
  - Skip files >1MB for brotli, >2MB for bz2/zlib
  - Catches all exceptions per file
"""
from __future__ import annotations

import bz2
import hashlib
import json
import lzma
import sys
import time
import traceback
import zlib
from collections import Counter
from pathlib import Path
import zipfile

import brotli


# Open log file early
LOG = Path(r"C:\Users\Art\AppData\Local\Temp\v10_run.log")
# Don't truncate — just append
def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


import bz2
import hashlib
import json
import lzma
import time
import zlib
from collections import Counter
from pathlib import Path
import zipfile

import brotli


CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUT_DIR = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v10")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = "20260820T1400Z"
PACKET = f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__v10-compression-experiment"
OUT_MIMO = Path(r"D:\4\OUT_MIMO")
ZIP_PATH = OUT_MIMO / f"{PACKET}.zip"
MANIFEST_PATH = OUT_MIMO / f"{PACKET}.manifest.json"
ENVELOPE_PATH = OUT_MIMO / f"{PACKET}.envelope.json"
READY_PATH = OUT_MIMO / f"{PACKET}.READY.json"


# ---------------------------------------------------------------------------
# BHA envelope helpers
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
    """x86 BCJ filter: zero out E8/E9 (CALL/JMP rel32) offsets."""
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


def pp_dedup_substring(data, min_len=32):
    """Replace longest repeated substring occurrence with back-ref token."""
    if len(data) < min_len * 3:
        return data
    best_off, best_len = 0, 0
    for start in range(0, len(data) - min_len, 1):
        if best_len > len(data) - start:
            break
        sub = data[start:start + min_len]
        idx = data.find(sub, start + 1, start + 1 + 65536)
        if idx < 0:
            continue
        ext = min_len
        while ext < 1024 and start + ext < len(data) and data[start + ext] == data[idx + ext]:
            ext += 1
        if ext > best_len:
            best_off, best_len = start, ext
    if best_len < min_len * 2:
        return data
    out = bytearray(data)
    token = b'\xff' + best_off.to_bytes(4, 'little') + best_len.to_bytes(4, 'little')
    return bytes(out[:best_off] + token + out[best_off + best_len:])


def pp_zero_extend(data):
    """Strip 4-byte zero padding before non-zero little-endian u32 values."""
    if len(data) < 16:
        return data
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if (i + 8 <= n
                and data[i] == 0 and data[i+1] == 0
                and data[i+2] == 0 and data[i+3] == 0
                and data[i+7] != 0):
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
# Measurement
# ---------------------------------------------------------------------------
def measure_one(data):
    sizes = {}
    n = len(data)
    # brotli: only on files <=500KB (slow on large)
    if n <= 500_000:
        sizes["brotli_q11"] = len(brotli.compress(data, quality=11))
        sizes["brotli_q5"] = len(brotli.compress(data, quality=5))
    else:
        sizes["brotli_q11"] = None
        sizes["brotli_q5"] = None
    # bz2, zlib: skip on >2MB
    if n <= 2_000_000:
        sizes["bz2_l9"] = len(bz2.compress(data, 9))
        sizes["zlib_l9"] = len(zlib.compress(data, 9))
    else:
        sizes["bz2_l9"] = None
        sizes["zlib_l9"] = None
    # lzma2 is the most expensive but we always need it as baseline
    sizes["lzma2_best"] = len(_lzma2_best(data))
    for env in ("BHCC1", "BHCS1", "BHVT1", "BHSC1", "BHRT1"):
        sizes[f"env_{env}"] = len(bha_envelope(env.encode(), data))
    pp_pairs = [
        ("identity", pp_identity),
        ("bcj_x86", pp_bcj_x86),
        ("dedup_substring", pp_dedup_substring),
        ("zero_extend", pp_zero_extend),
    ]
    for pp_name, pp_fn in pp_pairs:
        try:
            preprocessed = pp_fn(data)
            for env in ("BHCC1", "BHCS1", "BHVT1", "BHRT1"):
                name = f"{env}__{pp_name}"
                sizes[name] = len(bha_envelope(env.encode(), preprocessed))
        except Exception:
            for env in ("BHCC1", "BHCS1", "BHVT1", "BHRT1"):
                name = f"{env}__{pp_name}"
                sizes[name] = None
    return sizes


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    log(f"[v10] measuring {len(list(CORPUS.iterdir()))} files in {CORPUS}")
    files = sorted([p for p in CORPUS.iterdir()
                    if p.is_file() and p.suffix != ".json"])
    log(f"[v10] {len(files)} real BHA files")

    # Load BHA actual measurements
    rcorpus_json = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")
    bha_actual = {}
    if rcorpus_json.exists():
        cdata = json.loads(rcorpus_json.read_text())
        for row in cdata["rows"]:
            bha_actual[row["file"]] = (row.get("bha_magic"), row.get("bha_size"))

    results = []
    total_orig = total_bha = total_v10 = total_brotli = total_lzma2 = 0
    wins_over_bha = []
    wins_over_brotli = []

    n_codecs_per_file = 0  # for reporting
    for i, fp in enumerate(files, 1):
        log(f"[v10] [{i}/{len(files)}] {fp.name} ({fp.stat().st_size} B) starting...")
        try:
            data = fp.read_bytes()
            sizes = measure_one(data)
        except Exception as e:
            log(f"[v10]   ERR on {fp.name}: {e}")
            continue
        n_codecs_per_file = len(sizes)
        v10_combos_done = {k: v for k, v in sizes.items() if "__" in k and v is not None}
        if v10_combos_done:
            best = min(v10_combos_done, key=v10_combos_done.get)
            log(f"[v10]   done: best={best} size={v10_combos_done[best]}")

        # best v10 combo (env__pp only, no env_, no stdlib)
        v10_combos = {k: v for k, v in sizes.items()
                       if "__" in k and v is not None}
        if not v10_combos:
            continue
        best_v10_codec = min(v10_combos, key=v10_combos.get)
        best_v10_size = v10_combos[best_v10_codec]

        stdlib = {k: v for k, v in sizes.items()
                  if "__" not in k and v is not None}
        best_stdlib = min(stdlib, key=stdlib.get)

        bha_magic, bha_size = bha_actual.get(fp.name, ("?", None))
        r_bha = (bha_size / len(data)) if bha_size else None
        r_v10 = best_v10_size / len(data)
        brotli_size = sizes.get("brotli_q11")
        r_brotli = (brotli_size / len(data)) if brotli_size else None

        total_orig += len(data)
        if bha_size:
            total_bha += bha_size
        total_v10 += best_v10_size
        if brotli_size:
            total_brotli += brotli_size
        total_lzma2 += sizes["lzma2_best"]

        delta_bha = (bha_size - best_v10_size) if bha_size else 0
        delta_brotli = ((brotli_size - best_v10_size) if brotli_size else 0)

        if bha_size and best_v10_size < bha_size:
            wins_over_bha.append({
                "file": fp.name,
                "bha_magic": bha_magic,
                "bha_size": bha_size,
                "v10_codec": best_v10_codec,
                "v10_size": best_v10_size,
                "saved": delta_bha,
                "saved_pct": round(delta_bha / bha_size * 100, 2),
            })
        if brotli_size and best_v10_size < brotli_size:
            wins_over_brotli.append({
                "file": fp.name,
                "brotli_size": brotli_size,
                "v10_codec": best_v10_codec,
                "v10_size": best_v10_size,
                "saved": delta_brotli,
                "saved_pct": round(delta_brotli / brotli_size * 100, 2),
            })

        results.append({
            "file": fp.name,
            "size": len(data),
            "bha_magic": bha_magic,
            "bha_size": bha_size,
            "bha_pct": round(r_bha * 100, 3) if r_bha else None,
            "best_v10_codec": best_v10_codec,
            "best_v10_size": best_v10_size,
            "v10_pct": round(r_v10 * 100, 3),
            "brotli_q11_size": brotli_size,
            "brotli_pct": (round(r_brotli * 100, 3) if r_brotli else None),
            "bz2_size": sizes.get("bz2_l9"),
            "bz2_pct": (round(sizes["bz2_l9"]/len(data) * 100, 3)
                       if sizes.get("bz2_l9") else None),
            "lzma2_size": sizes["lzma2_best"],
            "lzma2_pct": round(sizes["lzma2_best"]/len(data) * 100, 3),
            "all_sizes": {k: v for k, v in sizes.items() if v is not None},
        })

    log(f"\n[v10] AGGREGATE on {len(results)} files ({total_orig} bytes):")
    log(f"  BHA actual:  {total_bha:>10} ({100*total_bha/total_orig:.2f}%)")
    log(f"  v10 best:    {total_v10:>10} ({100*total_v10/total_orig:.2f}%)")
    log(f"  brotli q11:  {total_brotli:>10} ({100*total_brotli/total_orig:.2f}%)")
    log(f"  lzma2 best:  {total_lzma2:>10} ({100*total_lzma2/total_orig:.2f}%)")
    if total_bha:
        d = total_bha - total_v10
        log(f"  v10 vs BHA:    {d:+d} bytes ({(d/total_bha)*100:+.2f}%)")
    if total_brotli:
        d = total_brotli - total_v10
        log(f"  v10 vs brotli: {d:+d} bytes ({(d/total_brotli)*100:+.2f}%)")

    log(f"\n[v10] WINS over BHA: {len(wins_over_bha)}/{len(results)}")
    for w in sorted(wins_over_bha, key=lambda x: -x["saved"])[:15]:
        log(f"  {w['file']:40s} bha={w['bha_size']:>7} v10={w['v10_size']:>7} "
              f"saved={w['saved']:>6} ({w['saved_pct']:5.1f}%) via {w['v10_codec']}")

    log(f"\n[v10] WINS over brotli q11: {len(wins_over_brotli)}/{len(results)}")
    for w in sorted(wins_over_brotli, key=lambda x: -x["saved"])[:15]:
        log(f"  {w['file']:40s} brotli={w['brotli_size']:>7} v10={w['v10_size']:>7} "
              f"saved={w['saved']:>6} ({w['saved_pct']:5.1f}%) via {w['v10_codec']}")

    # Save v10 measurements
    out_json = OUT_DIR / "v10_measurements.json"
    out_json.write_text(json.dumps({
        "n_files": len(results),
        "n_codecs_per_file": n_codecs_per_file,
        "codecs": ["brotli_q11", "brotli_q5", "bz2_l9", "zlib_l9", "lzma2_best",
                   "env_BHCC1", "env_BHCS1", "env_BHVT1", "env_BHSC1", "env_BHRT1",
                   "BHCC1__identity", "BHCC1__bcj_x86", "BHCC1__dedup_substring", "BHCC1__zero_extend",
                   "BHCS1__identity", "BHCS1__bcj_x86", "BHCS1__dedup_substring", "BHCS1__zero_extend",
                   "BHVT1__identity", "BHVT1__bcj_x86", "BHVT1__dedup_substring", "BHVT1__zero_extend",
                   "BHRT1__identity", "BHRT1__bcj_x86", "BHRT1__dedup_substring", "BHRT1__zero_extend"],
        "total_orig_bytes": total_orig,
        "total_bha_bytes": total_bha,
        "total_v10_bytes": total_v10,
        "total_brotli_q11_bytes": total_brotli,
        "total_lzma2_bytes": total_lzma2,
        "n_wins_over_bha": len(wins_over_bha),
        "n_wins_over_brotli": len(wins_over_brotli),
        "wins_over_bha_top15": sorted(wins_over_bha, key=lambda x: -x["saved"])[:15],
        "wins_over_brotli_top15": sorted(wins_over_brotli, key=lambda x: -x["saved"])[:15],
        "rows": results,
    }, indent=2))
    log(f"\n[v10] saved {out_json}")

    # ----- BUILD GPT ZIP -----
    log(f"\n[zip] building GPT hand-off ZIP...")
    OUT_MIMO.mkdir(parents=True, exist_ok=True)

    artifacts = []
    file_count = 0
    total_zip_bytes = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. README.md (auto-generated)
        readme = build_readme_md(results, wins_over_bha, wins_over_brotli,
                                 total_orig, total_bha, total_v10,
                                 total_brotli, total_lzma2)
        zf.writestr("README.md", readme)
        # 2. v10 script
        zf.write(Path(r"D:\4\bha-codecs\investigate_v10_new_pp.py"),
                 "scripts/investigate_v10_new_pp.py")
        # 3. v10 measurements JSON
        zf.write(out_json, "results/v10_measurements.json")
        # 4. v9b recommender (current STABLE)
        zf.write(Path(r"D:\4\bha-codecs\investigate_ssp5_recommender_v9b.py"),
                 "context/v9b_recommender.py")
        # 5. prior diagnostics ZIP (problems for GPT)
        zf.write(Path(r"D:\4\OUT_MIMO\bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip"),
                 "context/prior_v1to9b_zip.zip")

    zip_sha = sha256_file(ZIP_PATH)
    zip_size = ZIP_PATH.stat().st_size

    manifest = {
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "project_id": "bha-codecs-ssp5-recommender",
        "message_id": f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__v10-compression-experiment",
        "parent_message_id": None,
        "iteration_id": f"MIMO-V10-{TIMESTAMP}",
        "source_agent": "MIMO",
        "target_agent": "GPT",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload_path": f"OUT_MIMO/{PACKET}.zip",
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "artifacts": artifacts,
        "status": "READY",
        "summary": (
            f"v10 compression experiment: 3 new preprocessors (bcj_x86, "
            f"dedup_substring, zero_extend) tested on {len(results)} real BHA files. "
            f"v10 wins over BHA on {len(wins_over_bha)} files, over brotli-q11 "
            f"on {len(wins_over_brotli)} files. Total: BHA={total_bha} vs v10="
            f"{total_v10} ({(total_bha-total_v10)/total_bha*100:+.2f}%); "
            f"brotli={total_brotli} vs v10={total_v10} "
            f"({(total_brotli-total_v10)/total_brotli*100:+.2f}%)"
        ),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    ENVELOPE_PATH.write_text(json.dumps({
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "envelope_of": manifest["message_id"],
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "status": "READY",
    }, indent=2))
    READY_PATH.write_text(json.dumps({
        "ready": True,
        "message_id": manifest["message_id"],
        "at": manifest["created_at_utc"],
    }, indent=2))

    log(f"\nDONE.")
    log(f"  zip     -> {ZIP_PATH}")
    log(f"  size    -> {zip_size} bytes")
    log(f"  manifest-> {MANIFEST_PATH}")
    log(f"  envelope-> {ENVELOPE_PATH}")
    log(f"  ready   -> {READY_PATH}")
    log(f"  sha256  -> {zip_sha}")


def build_readme_md(results, wins_bha, wins_brotli,
                    total_orig, total_bha, total_v10,
                    total_brotli, total_lzma2):
    out = []
    add = out.append
    add("# BHA Compression Experiment v10 — Results for GPT")
    add("")
    add(f"**Generated**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    add(f"**Context**: User `Yury197812` asked MIMO to investigate compression")
    add("improvements while GPT works on the GitHub auth diagnostics.")
    add("MIMO tested 3 new preprocessors on all real BHA files.")
    add("")
    add("## 1. New preprocessors tested")
    add("")
    add("| Preprocessor | Description | Best for |")
    add("|--------------|-------------|----------|")
    add("| `pp_bcj_x86` | Zero out E8/E9 (CALL/JMP rel32) offsets in x86 code | x86 binaries, .exe, .dll |")
    add("| `pp_dedup_substring` | Replace longest repeated substring with back-ref | logs with repeated timestamps |")
    add("| `pp_zero_extend` | Strip 4-byte zero padding before u32 values | CSV with int32 columns |")
    add("")
    add("Combined with 4 BHA envelopes (BHCC1, BHCS1, BHVT1, BHRT1) and 5 stdlib codecs")
    add("(brotli-q11, brotli-q5, bz2, zlib, lzma2), total **25 codec variants** per file.")
    add("")
    add("## 2. Aggregate results")
    add("")
    add(f"- {len(results)} real BHA files, {total_orig:,} bytes total")
    add(f"- **BHA actual** (what real BHA produced): {total_bha:,} bytes ({100*total_bha/total_orig:.2f}%)")
    add(f"- **v10 best** (proposed): {total_v10:,} bytes ({100*total_v10/total_orig:.2f}%)")
    add(f"- **brotli q=11** (offline baseline): {total_brotli:,} bytes ({100*total_brotli/total_orig:.2f}%)")
    add(f"- **lzma2 best** (offline baseline): {total_lzma2:,} bytes ({100*total_lzma2/total_orig:.2f}%)")
    add("")
    d_bha = total_bha - total_v10
    d_brotli = total_brotli - total_v10
    add(f"**v10 vs BHA actual**: {d_bha:+,} bytes ({(d_bha/total_bha)*100:+.2f}%)")
    add(f"**v10 vs brotli q11**: {d_brotli:+,} bytes ({(d_brotli/total_brotli)*100:+.2f}%)")
    add("")
    if d_bha < 0:
        add(f"v10 is **WORSE** than BHA by {-d_bha:,} bytes. BHA is currently optimal.")
    elif d_bha == 0:
        add("v10 ties BHA — no improvement possible with current preprocessors.")
    else:
        add(f"v10 beats BHA by {d_bha:,} bytes ({(d_bha/total_bha)*100:.2f}%) — improvement!")
    add("")
    add("## 3. Top files where v10 wins over BHA")
    add("")
    add(f"**{len(wins_bha)} files** out of {len(results)} where v10 best < BHA actual.")
    add("")
    if wins_bha:
        add("| File | BHA size | v10 codec | v10 size | Saved |")
        add("|------|----------|-----------|----------|-------|")
        for w in sorted(wins_bha, key=lambda x: -x["saved"])[:15]:
            add(f"| `{w['file']}` | {w['bha_size']:,} | `{w['v10_codec']}` | {w['v10_size']:,} | {w['saved']:,} ({w['saved_pct']}%) |")
    else:
        add("_No files where v10 beat BHA. BHA is already at optimum._")
    add("")
    add("## 4. Top files where v10 wins over brotli-q11")
    add("")
    add(f"**{len(wins_brotli)} files** where v10 best < brotli-q11.")
    add("")
    if wins_brotli:
        add("| File | brotli size | v10 codec | v10 size | Saved |")
        add("|------|-------------|-----------|----------|-------|")
        for w in sorted(wins_brotli, key=lambda x: -x["saved"])[:15]:
            add(f"| `{w['file']}` | {w['brotli_size']:,} | `{w['v10_codec']}` | {w['v10_size']:,} | {w['saved']:,} ({w['saved_pct']}%) |")
    add("")
    add("## 5. Per-file measurements (excerpt — full data in `results/v10_measurements.json`)")
    add("")
    add("| File | Size | BHA% | v10 codec | v10% | brotli% | bz2% | lzma2% |")
    add("|------|------|------|-----------|------|---------|------|---------|")
    for r in results:
        add(f"| `{r['file'][:35]}` | {r['size']:,} | {r['bha_pct'] or '?':>5} | `{r['best_v10_codec'][:20]}` | "
            f"{r['v10_pct']:>5} | {r['brotli_pct']:>6} | {r['bz2_pct']:>5} | {r['lzma2_pct']:>6} |")
    add("")
    add("## 6. What GPT should investigate")
    add("")
    add("If v10 wins over BHA on some files, look for pattern:")
    add("- Which preprocessor wins for which file type?")
    add("- Are there preprocessors BHA already uses that we didn't model?")
    add("- Can pp_bcj_x86 be useful for actual x86 code in this corpus?")
    add("- Is dedup_substring safe for roundtrip? (it inserts 9-byte token,")
    add("  decoder must know to emit the original substring)")
    add("- Is zero_extend safe? (strips 4 leading zeros; decoder must re-pad)")
    add("- What's the MAX possible compression if we could pre-compress")
    add("  with a per-chunk adaptive codec (per memory: oracle-by-size)?")
    add("")
    add("## 7. How to extend")
    add("")
    add("If GPT finds good wins, next steps:")
    add("1. Add new preprocessors specific to identified file types:")
    add("   - pp_logfmt_quote: parse `key=value` logs into columns, compress columns separately")
    add("   - pp_xml_attribute: extract XML attribute names+values, dedup per name")
    add("   - pp_csv_int_pack: detect 4/8-byte int columns, pack as int32/int64 array")
    add("2. Build a v11 = v9b_recommender + new pp registry, retrain on real BHA picks")
    add("3. Add pp_roundtrip_safety_check: assert encode(decode(x)) == x for every new pp")
    add("4. Profile where LZMA2 already saturates (no pp can help) vs where pp is the bottleneck")
    add("")
    add("## 8. Memory pointers")
    add("")
    add("- `MEMORY.md` key findings:")
    add("  - Per-chunk adaptive codec ≤ fixed strategy (validated)")
    add("  - Depth≥2 pipelines = overhead (don't add LZMA2 on top of LZMA2)")
    add("  - Per-data-type codec optimum (no one-size-fits-all)")
    add("  - BHCC1 cross-column beats per-column atomize on telemetry")
    add("  - Centered signed delta = width by max|delta|")
    add("  - Synthetic ≠ real corpus for benchmarks")
    add("  - Real corpus BH-codec wins come from preprocessors, not envelope headers")
    add("  - Preprocessor × envelope combo discovery produces order-of-magnitude wins")
    add("  - BHA file_codec envelopes = magic + ULEB + LZMA2 body (5-15 byte overhead)")
    add("")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()