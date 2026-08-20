"""BHA LZMA max-compression benchmark — 1M rounds across full BHA TEST/ corpus.

Uses 47 corpus files from D:\4\bha-codecs\benchmark\\ to find max-compression
LZMA preset across realistic inputs.

Optimization: only tracks aggregate stats per (file, level) — no per-round
artifact. Trades per-round histogram for speed.
"""
from __future__ import annotations

import argparse
import json
import lzma
import statistics
import sys
import time
from pathlib import Path


CORPUS_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def load_corpus() -> dict:
    """Load all corpus files (skip directories and metadata)."""
    out = {}
    for p in sorted(CORPUS_DIR.glob("*")):
        if p.is_file() and p.suffix != ".jsonl" and p.name != "compress_methods.txt":
            out[p.name] = p.read_bytes()
    return out


def lzma_compress(data: bytes, level: int) -> tuple[bytes, int]:
    t0 = time.perf_counter()
    try:
        compressed = lzma.compress(data, format=lzma.FORMAT_XZ, preset=level)
    except lzma.LZMAError:
        return b"", 0
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return compressed, elapsed_ms


def lzma_round(data: bytes, level: int) -> tuple[int, int, int]:
    """Single round: returns (compressed_size, compress_ms, decompress_ms)."""
    comp, ms = lzma_compress(data, level)
    if not comp:
        return 0, 0, 0
    t0 = time.perf_counter()
    try:
        lzma.decompress(comp)
    except lzma.LZMAError:
        return 0, 0, 0
    dms = int((time.perf_counter() - t0) * 1000)
    return len(comp), ms, dms


def aliases(level: str) -> list[int]:
    table = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
             "6": 6, "7": 7, "8": 8, "9": 9, "e": lzma.PRESET_EXTREME}
    out = []
    for c in level.split(","):
        c = c.strip()
        if c not in table:
            print(f"  warning: unknown level '{c}', skipping")
            continue
        out.append(table[c])
    return out


def benchmark(corpus: dict, levels: list[int], rounds: int) -> dict:
    results = {}
    for fname, data in corpus.items():
        if not data:
            continue
        results[fname] = {"original_size": len(data), "levels": {}}
        for level in levels:
            label = f"L{level}" if level < 100 else "Lextreme"
            comp_sizes = []
            comp_ms = []
            dec_ms = []
            for r in range(rounds):
                cs, cms, dms = lzma_round(data, level)
                if cs == 0:
                    continue
                comp_sizes.append(cs)
                comp_ms.append(cms)
                dec_ms.append(dms)
            if not comp_sizes:
                continue
            results[fname]["levels"][label] = {
                "rounds": len(comp_sizes),
                "ratio_min_pct": round(min(comp_sizes) / len(data) * 100, 3),
                "ratio_max_pct": round(max(comp_sizes) / len(data) * 100, 3),
                "ratio_mean_pct": round(statistics.mean(comp_sizes) / len(data) * 100, 3),
                "compressed_mean_bytes": int(statistics.mean(comp_sizes)),
                "compress_ms_mean": round(statistics.mean(comp_ms), 2),
                "compress_ms_total": sum(comp_ms),
                "decompress_ms_mean": round(statistics.mean(dec_ms), 3),
            }
    return results


def pretty_print(results: dict, rounds: int):
    print(f"\nLZMA benchmark — {rounds} rounds per (file, level)")
    print("=" * 100)
    for fname, fdata in results.items():
        print(f"\n=== {fname} ({fdata['original_size']:,} bytes) ===")
        print(f"{'Level':10s} {'Rounds':>7s} {'Ratio%':>10s} {'Compress ms':>15s} {'Decompress ms':>15s}")
        print("-" * 100)
        for level_label, lvl in fdata["levels"].items():
            print(
                f"{level_label:10s} {lvl['rounds']:>7d} "
                f"{lvl['ratio_mean_pct']:>10.3f} "
                f"{lvl['compress_ms_mean']:>15.2f} "
                f"{lvl['decompress_ms_mean']:>15.3f}"
            )


def best_per_file(results: dict) -> dict:
    """For each file, find best (lowest ratio) level."""
    out = {}
    for fname, fdata in results.items():
        if not fdata["levels"]:
            continue
        best = min(fdata["levels"].items(), key=lambda kv: kv[1]["ratio_mean_pct"])
        out[fname] = {
            "original_bytes": fdata["original_size"],
            "best_level": best[0],
            "best_ratio_pct": best[1]["ratio_mean_pct"],
            "best_compressed_bytes": best[1]["compressed_mean_bytes"],
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1000000)
    parser.add_argument("--levels", default="0,1,2,3,4,5,6,7,8,9,e")
    parser.add_argument("--out", default="")
    parser.add_argument("--corpus", default=str(CORPUS_DIR))
    args = parser.parse_args()
    levels = aliases(args.levels)
    if not levels:
        print("no valid levels")
        return 1
    corpus = load_corpus()
    if not corpus:
        print(f"no corpus files in {args.corpus}")
        return 1
    print(f"corpus: {len(corpus)} files, levels={levels}, rounds={args.rounds}")
    total_compressions = len(corpus) * len(levels) * args.rounds
    print(f"total compressions: {total_compressions:,}")
    print(f"levels: {levels}")
    print(f"rounds per (file, level): {args.rounds:,}")
    print(f"total work: 11 levels × {len(corpus)} files × {args.rounds:,} rounds = {total_compressions:,} compressions")
    t0 = time.perf_counter()
    results = benchmark(corpus, levels, args.rounds)
    elapsed = time.perf_counter() - t0
    pretty_print(results, args.rounds)
    print(f"\ntotal benchmark time: {elapsed:.1f}s")
    print(f"total compressions: {total_compressions:,} in {elapsed:.1f}s = {total_compressions/elapsed:.0f}/s")
    best = best_per_file(results)
    print(f"\nBest (lowest ratio) per file:")
    print(f"{'File':50s} {'Level':10s} {'Ratio%':>10s} {'Bytes':>10s}")
    print("-" * 100)
    for fname, b in sorted(best.items(), key=lambda x: x[1]["best_ratio_pct"]):
        print(f"{fname:50s} {b['best_level']:10s} {b['best_ratio_pct']:>10.3f} {b['best_compressed_bytes']:>10d}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "rounds": args.rounds,
                "levels": args.levels,
                "elapsed_seconds": round(elapsed, 1),
                "total_compressions": total_compressions,
                "best_per_file": best,
                "results": results,
            }, f, indent=2)
        print(f"\nresults written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
