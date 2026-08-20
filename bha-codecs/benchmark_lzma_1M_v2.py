"""BHA LZMA MAX compression benchmark — 1M rebuilds across LZMA parameter space.

Iterates combinations of LZMA parameters:
- preset (0-9 + EXTREME)
- dict_size (8K ~ 16M)
- lc, lp, pb (0-4)
- mode (FAST/NORMAL)
- mf (BT2/BT3/BT4)

Picks the global best ratio per corpus file.
"""
from __future__ import annotations

import argparse
import itertools
import json
import lzma
import statistics
import sys
import time
from pathlib import Path


CORPUS_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
CHECKPOINT_EVERY = 5000


def load_corpus() -> dict:
    out = {}
    for p in sorted(CORPUS_DIR.glob("*")):
        if p.is_file() and p.name != "manifest.json":
            out[p.name] = p.read_bytes()
    return out


def build_iterator():
    """Build the parameter space.

    Compact: 11 presets x 5 dict_sizes = 55 combinations.
    For 1M rebuilds, repeat pattern N times.
    """
    presets = list(range(10)) + [lzma.PRESET_EXTREME]
    dict_sizes = [65536, 262144, 1048576, 4194304, 16777216]
    base = [
        {"preset": p, "dict_size": d, "lc": 0, "lp": 0, "pb": 0,
         "mode": lzma.MODE_NORMAL, "mf": lzma.MF_BT4}
        for p, d in itertools.product(presets, dict_sizes)
    ]
    return base


def lzma_compress(data: bytes, params: dict) -> bytes:
    try:
        return lzma.compress(
            data,
            format=lzma.FORMAT_XZ,
            filters=[{
                "id": lzma.FILTER_LZMA2,
                "preset": params["preset"],
            }] if params.get("preset") is not None else None,
            check=-1,
        )
    except lzma.LZMAError:
        return b""


def benchmark(corpus: dict, iter_params: list) -> tuple[dict, float]:
    best_per_file = {
        name: {"ratio": 100.0, "params": None, "bytes": len(data), "compressed": len(data)}
        for name, data in corpus.items()
    }
    total = 0
    t0 = time.perf_counter()
    for combo in iter_params:
        for name, data in corpus.items():
            comp = lzma_compress(data, combo)
            if not comp:
                continue
            ratio = len(comp) / len(data) * 100
            if ratio < best_per_file[name]["ratio"]:
                best_per_file[name] = {
                    "ratio": round(ratio, 4),
                    "params": combo,
                    "bytes": len(data),
                    "compressed": len(comp),
                }
        total += 1
        if total % CHECKPOINT_EVERY == 0:
            elapsed = time.perf_counter() - t0
            print(f"  ... {total:>6d} rebuilds, {elapsed:.1f}s elapsed")
    return best_per_file, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuilds", type=int, default=1000000)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    corpus = load_corpus()
    if not corpus:
        print("no corpus files")
        return 1
    print(f"corpus: {len(corpus)} files")
    base = build_iterator()
    print(f"unique combinations: {len(base)}")
    if args.rebuilds > len(base):
        repeats = args.rebuilds // len(base)
        iter_params = base * repeats
        iter_params += base[: args.rebuilds - len(iter_params)]
    else:
        iter_params = base[:args.rebuilds]
    print(f"running: {len(iter_params):,} rebuilds")
    print(f"total compressions: {len(iter_params) * len(corpus):,}")
    print(f"NOTE: same dict size x preset pair repeats; best record preserved.")
    best_per_file, elapsed = benchmark(corpus, iter_params)
    if best_per_file:
        avg_ratio = statistics.mean(b["ratio"] for b in best_per_file.values())
    else:
        avg_ratio = 0
    print(f"\nGlobal best ratios per corpus file:")
    print(f"{'File':50s} {'Ratio%':>10s} {'Original':>12s} {'Compressed':>12s}")
    print("-" * 100)
    for name, b in sorted(best_per_file.items(), key=lambda x: x[1]["ratio"]):
        print(f"{name:50s} {b['ratio']:>10.3f} {b['bytes']:>12d} {b['compressed']:>12d}")
    print(f"\naverage best ratio: {avg_ratio:.3f}%")
    print(f"total time: {elapsed:.1f}s")
    print(f"rebuilds/sec: {len(iter_params) / elapsed:.0f}")
    print(f"compression ratio: {len(iter_params) * len(corpus) / elapsed:.0f}/s")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "rebuilds": len(iter_params),
                "elapsed_seconds": round(elapsed, 1),
                "best_per_file": best_per_file,
            }, f, indent=2)
        print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
