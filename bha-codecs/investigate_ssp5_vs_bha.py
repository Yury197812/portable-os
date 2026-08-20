"""Investigation L: real BHA archive via direct import + side-by-side benchmark.

Imports D:\\PROJECT UNIVERSE\\01Compression\\BHA\\black_hole_archiver.py as `bha`
and calls its _compress_best() on the same TEST corpus files we used in
investigations F..K. This gives a true apples-to-apples comparison: BHA's
ensemble pipeline vs our adaptive_atomize / ssp5 stack.
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

BHA_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA")
sys.path.insert(0, str(BHA_DIR))
import black_hole_archiver as bha  # noqa: E402

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_even_atom import (
    atomize_integers, ssp5_encode, ssp5_decode,
    deatomize_integers, gen_even_mask_zero, gen_even_mask_one,
    gen_arbitrary, gen_arbitrary_mixed,
)
from investigate_ssp5_adaptive import adaptive_atomize, deadaptive_atomize
from investigate_ssp5_real_corpus import CORPUS, extract_ints_dense_csv, extract_ints_telemetry

import lzma
import struct

OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-vs-bha")
OUT.mkdir(parents=True, exist_ok=True)


def _int_stream(values):
    return b"".join(struct.pack("<q", v) for v in values)


SOURCES = [
    ("dense_numeric_csv_300k.csv", lambda p: p.read_bytes()[:200_000], ".csv"),
    ("telemetry_logs_1m.log",       lambda p: p.read_bytes()[:200_000], ".log"),
    ("data_json_100k.json",         lambda p: p.read_bytes(),          ".json"),
    ("ini_config_128k.ini",         lambda p: p.read_bytes()[:100_000], ".ini"),
    ("css_repeated_150k.css",       lambda p: p.read_bytes(),          ".css"),
    ("log_long_repeated_512k.log",  lambda p: p.read_bytes()[:200_000], ".log"),
    ("img_smooth_256x256.raw",      lambda p: p.read_bytes()[:200_000], ".raw"),
    ("random_lcg_256k.bin",         lambda p: p.read_bytes()[:200_000], ".bin"),
    ("repeating_binary_pattern.bin",lambda p: p.read_bytes()[:200_000], ".bin"),
    ("sparse_many_columns_300k.csv",lambda p: p.read_bytes()[:200_000], ".csv"),
    ("zero_sparse_binary_128k.bin", lambda p: p.read_bytes(),          ".bin"),
]


def _our_pipeline(data: bytes) -> bytes:
    """Our best-effort pipeline: adaptive_atomize -> ssp5 envelope."""
    if len(data) % 8 == 0:
        n = len(data) // 8
        try:
            vals = list(struct.unpack("<" + "q" * n, data))
            adapt = adaptive_atomize(vals, chunk=4096)
            return ssp5_encode(adapt)
        except Exception:
            pass
    return ssp5_encode(data)


def _our_pipeline_with_lzma(data: bytes) -> bytes:
    """Alternative: just LZMA2 extreme without our atomize (control)."""
    best = None
    for p in (6, 9 | lzma.PRESET_EXTREME):
        c = lzma.compress(data, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": p}])
        if best is None or len(c) < len(best):
            best = c
    return best


def main():
    # Force runtime to load (may raise if DLL missing)
    try:
        ssp = bha._load_runtime()
        print(f"[L] BHA runtime loaded: {ssp.__name__}")
    except Exception as e:
        print(f"[L] BHA runtime load FAILED: {e}")
        print("Skipping real BHA comparison; will only compare with size model.")
        ssp = None

    rows = []
    for fname, fn, ext in SOURCES:
        path = CORPUS / fname
        if not path.exists():
            continue
        data = fn(path)
        orig = len(data)

        # --- our pipeline ---
        t0 = time.perf_counter()
        try:
            ours = _our_pipeline(data)
            ours_size = len(ours)
            ours_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            ours_size = None
            ours_ms = None
            ours = None

        # --- lzma2 extreme control ---
        try:
            lzma_size = len(_our_pipeline_with_lzma(data))
        except Exception:
            lzma_size = None

        # --- real BHA archive ---
        bha_size = None
        bha_ms = None
        bha_archive = None
        bha_magic = None
        if ssp is not None:
            t0 = time.perf_counter()
            try:
                bha_archive, _ = bha._compress_best(data, path)
                bha_size = len(bha_archive)
                bha_ms = (time.perf_counter() - t0) * 1000
                if bha_archive:
                    # Identify leading magic
                    m = bha_archive[:5]
                    bha_magic = m.split(b"\x00", 1)[0].decode("ascii", errors="replace")
            except Exception as e:
                bha_size = f"err:{str(e)[:40]}"

        rows.append({
            "file": fname,
            "ext": ext,
            "orig": orig,
            "ours_size": ours_size,
            "ours_ms": round(ours_ms, 1) if ours_ms else None,
            "lzma2_size": lzma_size,
            "bha_size": bha_size,
            "bha_ms": round(bha_ms, 1) if bha_ms else None,
            "bha_magic": bha_magic,
            "ours_pct": round(100 * ours_size / orig, 2) if ours_size else None,
            "lzma2_pct": round(100 * lzma_size / orig, 2) if lzma_size else None,
            "bha_pct": round(100 * bha_size / orig, 2) if isinstance(bha_size, int) else None,
        })
        print(f"\n{fname} ({ext})")
        print(f"  orig:     {orig}")
        print(f"  ours:     {ours_size}  ({rows[-1]['ours_pct']}%)  {rows[-1]['ours_ms']}ms")
        print(f"  lzma2:    {lzma_size}  ({rows[-1]['lzma2_pct']}%)")
        print(f"  bha:      {bha_size}  ({rows[-1]['bha_pct']}%)  {rows[-1]['bha_ms']}ms  magic={bha_magic}")

    out_json = OUT / "ours-vs-bha.json"
    out_json.write_text(json.dumps(rows, indent=2))
    print(f"\nresults -> {out_json}")

    # Summary: when does BHA win, when do we win?
    wins = {"bha": 0, "ours": 0, "tie": 0}
    for r in rows:
        if r["ours_size"] is None or not isinstance(r["bha_size"], int):
            continue
        if r["bha_size"] < r["ours_size"]:
            wins["bha"] += 1
        elif r["ours_size"] < r["bha_size"]:
            wins["ours"] += 1
        else:
            wins["tie"] += 1
    print(f"\n--- winner by smallest size: BHA={wins['bha']}, "
          f"ours={wins['ours']}, tie={wins['tie']} ---")


if __name__ == "__main__":
    main()