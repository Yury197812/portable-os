"""BHA LZMA max-compression benchmark — runs N rounds across LZMA levels.

Tests: archive a payload (TEXT and ALREADY-COMPRESSED test files) using
LZMA levels 0-9, |extreme (LZMA_PRESET_EXTREME), |dict_size variants.

Goal: find the BEST ratio across levels, identify the level/round that
yields the maximum compression for our pipeline.

Usage:
    python bha_lzma_max.py --rounds 1000 --levels 0,1,2,3,4,5,6,7,8,9,e
    python bha_lzma_max.py --rounds 100 --levels 6,9,e --algo lzma
"""
from __future__ import annotations

import argparse
import json
import lzma
import statistics
import sys
import time
from pathlib import Path


# Base test content (replicated from D:\4\oeis-classifier\taxonomy.json + sample sequences)
TEST_PAYLOADS = {
    "taxonomy": b"",  # loaded later
    "bha_catalog": b"",  # loaded later
    "oeis_html": b"",  # loaded later
    "cpu_html": b"",  # loaded later
}


def load_payloads() -> dict:
    """Load real-world payloads from D:\4."""
    out = {}
    candidates = {
        "taxonomy": Path(r"D:\4\oeis-classifier\taxonomy.json"),
        "bha_catalog": Path(r"D:\4\bha-codecs\catalog.ini"),
        "oeis_html": None,
        "cpu_html": Path(r"D:\4\docs\cpu-recommendation-2026-08-19.html"),
        "bha_codegen": Path(r"D:\4\OUT\MIMO\genome\component_genome.py"),
    }
    # pick an existing OEIS HTML
    details_dir = Path(r"D:\4\oeis\details")
    if details_dir.exists():
        for p in details_dir.glob("A0000*.html"):
            candidates["oeis_html"] = p
            break
    for name, path in candidates.items():
        if path and path.exists():
            out[name] = path.read_bytes()
    return out


def lzma_compress(data: bytes, level: int) -> tuple[bytes, int]:
    """Compress with LZMA. Returns (compressed, elapsed_ms)."""
    t0 = time.perf_counter()
    try:
        opts = {"format": lzma.FORMAT_XZ, "preset": level}
        compressed = lzma.compress(data, **opts)
    except lzma.LZMAError as e:
        return b"", 0
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return compressed, elapsed_ms


def lzma_decompress(data: bytes) -> int:
    """Decompress; returns elapsed_ms."""
    t0 = time.perf_counter()
    try:
        lzma.decompress(data)
    except lzma.LZMAError:
        return 0
    return int((time.perf_counter() - t0) * 1000)


def aliases(level: str) -> list[int]:
    """Return LZMA preset integers for the given level alias."""
    table = {
        "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        "6": 6, "7": 7, "8": 8, "9": 9,
        "e": lzma.PRESET_EXTREME,
        "max": lzma.PRESET_EXTREME,
    }
    levels = [c.strip() for c in level.split(",")]
    out = []
    for l in levels:
        if l not in table:
            print(f"  warning: unknown level alias '{l}', skipping")
            continue
        out.append(table[l])
    return out


def benchmark(payloads: dict, levels: list[int], rounds: int) -> dict:
    """Run rounds=N for each payload x level, return aggregated stats."""
    results = {}
    for pl_name, pl_data in payloads.items():
        if not pl_data:
            continue
        original_size = len(pl_data)
        results[pl_name] = {
            "original_size": original_size,
            "levels": {},
        }
        for level in levels:
            label = f"L{level}" if level < 99 else "Lextreme"
            ratios = []
            times = []
            dc_times = []
            for r in range(rounds):
                comp, ms = lzma_compress(pl_data, level)
                if not comp:
                    continue
                ratios.append(len(comp) / original_size * 100)
                times.append(ms)
                dc_ms = lzma_decompress(comp)
                dc_times.append(dc_ms)
            if not ratios:
                continue
            results[pl_name]["levels"][label] = {
                "rounds": len(ratios),
                "ratio_min_pct": round(min(ratios), 3),
                "ratio_max_pct": round(max(ratios), 3),
                "ratio_mean_pct": round(statistics.mean(ratios), 3),
                "compress_ms_min": min(times),
                "compress_ms_mean": round(statistics.mean(times), 1),
                "compress_ms_max": max(times),
                "decompress_ms_mean": round(statistics.mean(dc_times), 1),
            }
    return results


def pretty_print(results: dict, rounds: int) -> None:
    print(f"\nLZMA benchmark — {rounds} rounds per (payload, level)")
    print("=" * 90)
    for pl_name, pl_data in results.items():
        if not pl_data:
            continue
        print(f"\n=== {pl_name} ({pl_data['original_size']} bytes) ===")
        header = f"{'Level':10s} {'Rounds':>7s} {'Ratio%':>10s} {'Compress ms':>15s} {'Decompress ms':>15s}"
        print(header)
        print("-" * 90)
        for level_label, lvl in pl_data["levels"].items():
            print(
                f"{level_label:10s} {lvl['rounds']:>7d} "
                f"{lvl['ratio_mean_pct']:>10.3f} "
                f"{lvl['compress_ms_mean']:>15.1f} "
                f"{lvl['decompress_ms_mean']:>15.1f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--levels", default="0,1,3,6,9,e")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()
    levels = aliases(args.levels)
    if not levels:
        print("no valid levels")
        return 1
    payload_paths = load_payloads()
    if not payload_paths:
        print("no payloads found")
        return 1
    print(f"loading {len(payload_paths)} payloads, levels={levels}")
    t0 = time.perf_counter()
    results = benchmark(payload_paths, levels, args.rounds)
    elapsed = time.perf_counter() - t0
    pretty_print(results, args.rounds)
    print(f"\ntotal benchmark time: {elapsed:.1f}s")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "rounds": args.rounds,
                "levels": args.levels,
                "elapsed_seconds": round(elapsed, 1),
                "results": results,
            }, f, indent=2)
        print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
