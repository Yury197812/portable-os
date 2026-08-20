"""BHA corpus benchmark — runs archive + extract on every file in TEST/,
measures SHA-256 round-trip, records ratio and elapsed time. Output JSONL to stdout.

Usage:
    python benchmark_bha_corpus.py > corpus_results.jsonl
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

BHA_CLI = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py")
TEST_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUT_DIR = Path(r"D:\4\bha-codecs\benchmark")
LIMIT_PER_FILE = 5_000_000  # 5 MB cap per archive to skip 10MB single_giant_line_record


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_bha(args: list[str], timeout: int = 60) -> tuple[int, str, str, float]:
    t0 = time.time()
    try:
        cp = subprocess.run(
            [sys.executable, str(BHA_CLI), *args],
            cwd=str(BHA_CLI.parent),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return cp.returncode, cp.stdout, cp.stderr, (time.time() - t0) * 1000
    except subprocess.TimeoutExpired:
        return -1, "", "timeout", (time.time() - t0) * 1000


def benchmark_one(file_path: Path) -> dict:
    src_bytes = file_path.read_bytes()
    src_size = len(src_bytes)
    src_sha = sha256(src_bytes)
    if src_size > LIMIT_PER_FILE:
        return {
            "file": file_path.name,
            "skipped": True,
            "reason": "size_limit",
            "size": src_size,
        }
    out_dir = OUT_DIR / file_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    bha = out_dir / (file_path.name + ".bha")
    extracted = out_dir / (file_path.name + ".extracted")

    rc, out, err, ms = run_bha(["archive", str(file_path), str(bha)])
    if rc != 0:
        return {
            "file": file_path.name,
            "size": src_size,
            "sha256": src_sha,
            "archive_failed": True,
            "archive_rc": rc,
            "archive_stderr": err.strip()[:300],
        }
    bha_size = bha.stat().st_size
    ratio_pct = round(bha_size / src_size * 100, 2)
    rc2, out2, err2, ms2 = run_bha(["extract", str(bha)])
    extracted_path = None
    m = re.search(r"output:\s*(.+)", out2)
    if m:
        extracted_path = Path(m.group(1).strip())
    if not extracted_path or not extracted_path.exists():
        return {
            "file": file_path.name,
            "size": src_size,
            "sha256": src_sha,
            "archive_bytes": bha_size,
            "ratio_pct": ratio_pct,
            "archive_ms": round(ms, 1),
            "extract_failed": True,
            "extract_stderr": err2.strip()[:300],
        }
    extracted_bytes = extracted_path.read_bytes()
    extracted_sha = sha256(extracted_bytes)
    round_trip_match = extracted_sha == src_sha
    extracted_path.unlink()
    bha.unlink()
    return {
        "file": file_path.name,
        "size": src_size,
        "sha256": src_sha,
        "archive_bytes": bha_size,
        "ratio_pct": ratio_pct,
        "archive_ms": round(ms, 1),
        "extract_ms": round(ms2, 1),
        "round_trip_match": round_trip_match,
        "extracted_sha": extracted_sha,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(TEST_DIR.glob("*"))
    files = [f for f in files if f.is_file() and f.suffix != ".json" or f.name == "manifest.json"]
    files = [f for f in files if f.name != "manifest.json"]
    print(f"benchmarking {len(files)} files", file=sys.stderr)
    for f in files:
        rec = benchmark_one(f)
        print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
