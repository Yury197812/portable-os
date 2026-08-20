"""Test archive test: original vs re-compressed (already-archived) files.

Compares compression ratio when:
- LZMA applied to original file
- LZMA applied to file that was already compressed by zip/gzip/bha/bzip2

Hypothesis: re-compressing an archive gives minimal gain because
random-like distribution limits LZMA's window. The test reveals
the diminishing returns of nested compression.
"""
from __future__ import annotations

import json
import lzma
import gzip
import time
import zipfile
import io
import sys
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
RESULTS = []


def compress_lzma(data, level=9):
    try:
        return lzma.compress(data, format=lzma.FORMAT_XZ,
                              filters=[{"id": lzma.FILTER_LZMA2, "preset": level}],
                              check=-1)
    except Exception:
        return b""


def compress_gzip(data, level=9):
    return gzip.compress(data, compresslevel=level)


def test_single_file(filepath, max_size=2_000_000):
    if filepath.stat().st_size > max_size:
        return None
    original_data = filepath.read_bytes()
    original_size = len(original_data)
    lzma_size = len(compress_lzma(original_data))
    gzip_size = len(compress_gzip(original_data))
    return {
        "file": filepath.name,
        "original": original_size,
        "lzma_ratio": round(lzma_size / original_size * 100, 2),
        "gzip_ratio": round(gzip_size / original_size * 100, 2),
    }


def test_recompress_archives():
    """Test: compress file, then re-compress the compressed archive."""
    samples = ["data_csv_100k.csv", "log_high_entropy_tail_512k.log", "binary_header_text_payload.log"]
    results = []
    for name in samples:
        path = CORPUS / name
        if not path.exists():
            continue
        original = path.read_bytes()
        lzma1 = compress_lzma(original)
        gzip1 = compress_gzip(original)
        lzma2 = compress_lzma(lzma1)
        gzip2 = compress_gzip(lzma1)
        lzma3 = compress_lzma(gzip1)
        results.append({
            "file": name,
            "original": len(original),
            "first_lzma": len(lzma1),
            "first_lzma_ratio": round(len(lzma1) / len(original) * 100, 2),
            "second_lzma_of_lzma": len(lzma2),
            "second_lzma_ratio": round(len(lzma2) / len(lzma1) * 100, 2),
            "first_gzip": len(gzip1),
            "first_gzip_ratio": round(len(gzip1) / len(original) * 100, 2),
            "second_lzma_of_gzip": len(lzma3),
            "second_lzma_of_gzip_ratio": round(len(lzma3) / len(gzip1) * 100, 2),
        })
    return results


def test_real_archives():
    """Test: read already-compressed files (zip/gzip)."""
    results = []
    test_files = list(CORPUS.glob("*"))
    for path in test_files[:5]:
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        try:
            with open(path, "rb") as f:
                data = f.read()
            if path.suffix in [".zip", ".gz", ".bz2", ".7z", ".xz"]:
                lzma_size = len(compress_lzma(data))
                results.append({
                    "file": path.name,
                    "type": "pre-archived",
                    "original": len(data),
                    "lzma_ratio": round(lzma_size / len(data) * 100, 2),
                })
        except Exception:
            pass
    return results


def main() -> int:
    print("=== Test 1: Original files → LZMA / gzip ===")
    sample_files = [
        "data_csv_100k.csv", "data_json_100k.json", "log_long_repeated_512k.log",
        "binary_header_text_payload.log", "random_lcg_256k.bin",
        "truncated_partial_last_block.bin", "html_inline_data_uri_200k.html",
        "css_repeated_150k.css", "xml_attrs_300k.xml", "ini_config_128k.ini"
    ]
    results = []
    for name in sample_files:
        path = CORPUS / name
        if path.exists():
            r = test_single_file(path, 5_000_000)
            if r:
                results.append(r)
                print(f"  {r['file']:50s}: original={r['original']:>10d}  lzma={r['lzma_ratio']:>6.2f}%  gzip={r['gzip_ratio']:>6.2f}%")
    print(f"\n{len(results)} files tested")
    print()
    print("=== Test 2: Recompressing already-archived data ===")
    recompress = test_recompress_archives()
    for r in recompress:
        print(f"  {r['file']}:")
        print(f"    original: {r['original']:>10d} bytes")
        print(f"    first LZMA: {r['first_lzma']:>10d} ({r['first_lzma_ratio']}%)")
        print(f"    LZMA of LZMA: {r['second_lzma_of_lzma']:>10d} ({r['second_lzma_ratio']}%)  [{(r['first_lzma'] - r['second_lzma_of_lzma'])} bytes saved]")
        print(f"    first gzip: {r['first_gzip']:>10d} ({r['first_gzip_ratio']}%)")
        print(f"    LZMA of gzip: {r['second_lzma_of_gzip']:>10d} ({r['second_lzma_of_gzip_ratio']}%)  [{(r['first_gzip'] - r['second_lzma_of_gzip'])} bytes saved]")
    print()
    print("=== Test 3: Already-archived files in corpus ===")
    pre_archived = test_real_archives()
    for r in pre_archived:
        print(f"  {r['file']} ({r['type']}): original={r['original']}  lzma={r['lzma_ratio']}%")
    out = {
        "n_samples": len(results),
        "results": results,
        "recompress": recompress,
        "pre_archived": pre_archived,
    }
    out_path = Path(r"D:\4\bha-codecs\benchmark\archive-test-results.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8-sig")
    print(f"\nresults saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
