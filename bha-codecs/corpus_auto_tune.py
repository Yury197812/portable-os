"""Compression suite — corpus-wide auto-tune.

Tests 7 variants (lzma_fast, lzma_default, lzma_extreme, gzip_default,
zip_default, atomized_lzma, atomized_gzip) on 50 corpus files.
Returns best per file with strategy.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import lzma
import sys
import time
import zipfile
from pathlib import Path


CORPUS_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
SKILL_BENCHMARK = Path(r"C:\Users\Art\.mimicode\skills\archive-benchmark\scripts\archive_benchmark.py")
SKILL_COMPARATOR = Path(r"C:\Users\Art\.mimicode\skills\archive-strategy-comparator\scripts\archive_strategy_comparator_v2.py")


def load_corpus() -> dict:
    out = {}
    for p in sorted(CORPUS_DIR.glob("*")):
        if p.is_file() and p.name != "manifest.json":
            out[p.name] = p.read_bytes()
    return out


def compress_lzma(data: bytes, preset: int) -> bytes:
    try:
        return lzma.compress(
            data, format=lzma.FORMAT_XZ,
            filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}],
            check=-1,
        )
    except lzma.LZMAError:
        return b""


def decompress_lzma(data: bytes) -> bytes:
    try:
        return lzma.decompress(data)
    except Exception:
        return b""


def compress_gzip(data: bytes, level: int) -> bytes:
    try:
        return gzip.compress(data, compresslevel=level)
    except Exception:
        return b""


def compress_zip(data: bytes, level: int) -> bytes:
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as zf:
            zf.writestr("data", data)
        return buf.getvalue()
    except Exception:
        return b""


def atomize_simple(data: bytes) -> bytes:
    """Quick atomization — try CSV/JSON/keyvalue."""
    try:
        sample = data[:5000].decode("utf-8", errors="replace")
        import csv, json as _json, re
        if "," in sample and "\n" in sample:
            rows = list(csv.reader(io.StringIO(sample)))
            if len(rows) > 1 and len(rows[0]) >= 2:
                return data
        if sample.lstrip().startswith(("{", "[")):
            try:
                _json.loads(sample)
                return data
            except Exception:
                pass
        if "=" in sample:
            return data
    except Exception:
        pass
    return data


def benchmark_variant(variant: str, data: bytes) -> tuple[int, int, int]:
    """Returns (compressed_size, compress_ms, decompress_ms)."""
    if variant == "lzma_fast":
        src = data
        t0 = time.perf_counter()
        comp = compress_lzma(src, 3)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        t0 = time.perf_counter()
        decompress_lzma(comp)
        return len(comp), cms, int((time.perf_counter() - t0) * 1000)
    if variant == "lzma_default":
        src = data
        t0 = time.perf_counter()
        comp = compress_lzma(src, 6)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        t0 = time.perf_counter()
        decompress_lzma(comp)
        return len(comp), cms, int((time.perf_counter() - t0) * 1000)
    if variant == "lzma_extreme":
        src = data
        t0 = time.perf_counter()
        comp = compress_lzma(src, lzma.PRESET_EXTREME)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        t0 = time.perf_counter()
        decompress_lzma(comp)
        return len(comp), cms, int((time.perf_counter() - t0) * 1000)
    if variant == "gzip_default":
        src = data
        t0 = time.perf_counter()
        comp = compress_gzip(src, 6)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        t0 = time.perf_counter()
        gzip.decompress(comp)
        return len(comp), cms, int((time.perf_counter() - t0) * 1000)
    if variant == "zip_default":
        src = data
        t0 = time.perf_counter()
        comp = compress_zip(src, 6)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        t0 = time.perf_counter()
        buf = io.BytesIO(comp)
        with zipfile.ZipFile(buf) as zf:
            zf.read("data")
        return len(comp), cms, int((time.perf_counter() - t0) * 1000)
    if variant == "atomized_lzma":
        src = atomize_simple(data)
        t0 = time.perf_counter()
        comp = compress_lzma(src, lzma.PRESET_EXTREME)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        return len(comp), cms, 0
    if variant == "atomized_gzip":
        src = atomize_simple(data)
        t0 = time.perf_counter()
        comp = compress_gzip(src, 6)
        cms = int((time.perf_counter() - t0) * 1000)
        if not comp:
            return 0, cms, 0
        return len(comp), cms, 0
    return 0, 0, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="lzma_fast,lzma_default,lzma_extreme,gzip_default,zip_default,atomized_lzma,atomized_gzip")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()
    variants = [v.strip() for v in args.variants.split(",")]
    corpus = load_corpus()
    if not corpus:
        print("no corpus files")
        return 1
    print(f"corpus: {len(corpus)} files, variants: {len(variants)}, rounds: {args.rounds}")
    total_compressions = len(corpus) * len(variants) * args.rounds
    print(f"total compressions: {total_compressions}")
    best_per_file = {}
    t0 = time.perf_counter()
    for variant in variants:
        for name, data in corpus.items():
            best_size = best_per_file.get(name, {}).get("compressed_size", float("inf"))
            for r in range(args.rounds):
                comp, cms, dms = benchmark_variant(variant, data)
                if comp and comp < best_size:
                    best_per_file[name] = {
                        "variant": variant,
                        "compressed_size": comp,
                        "ratio_pct": round(comp / max(len(data), 1) * 100, 3),
                        "compress_ms": cms,
                        "decompress_ms": dms,
                        "original_size": len(data),
                    }
                    best_size = comp
        elapsed = time.perf_counter() - t0
        print(f"  {variant}: {elapsed:.0f}s elapsed")
    elapsed = time.perf_counter() - t0
    print(f"\ntotal: {elapsed:.0f}s, {total_compressions} compressions, {total_compressions/elapsed:.0f}/s")
    print(f"best per file ({len(best_per_file)} files):")
    print(f"{'File':50s} {'Variant':20s} {'Ratio%':>10s} {'Bytes':>10s}")
    print("-" * 95)
    by_ratio = sorted(best_per_file.items(), key=lambda x: x[1]["ratio_pct"])
    for name, b in by_ratio:
        print(f"{name:50s} {b['variant']:20s} {b['ratio_pct']:>10.3f} {b['compressed_size']:>10d}")
    avg_ratio = sum(b["ratio_pct"] for b in best_per_file.values()) / len(best_per_file)
    print(f"\naverage best ratio: {avg_ratio:.3f}%")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "elapsed_seconds": round(elapsed, 1),
                "total_compressions": total_compressions,
                "variants_tested": variants,
                "rounds": args.rounds,
                "best_per_file": best_per_file,
                "average_best_ratio_pct": round(avg_ratio, 3),
            }, f, indent=2)
        print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
