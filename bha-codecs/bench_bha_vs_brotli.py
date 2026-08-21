"""BHA vs Brotli: side-by-side on Brotli-friendly content.

Compares our BHA archiver vs system brotli (Python brotli bindings) on
textual/web content — the domain where brotli is the standard.

For each input:
  - raw size
  - brotli q=6 / q=11 size + ratio + pack_ms + decode_ms
  - BHA size (via bha_cli.py benchmark) + ratio + pack_ms
  - verdict: who wins
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import brotli


BHA_CLI = r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py"
OUT_JSON = Path(r"D:\4\bha-codecs\benchmark\bha_vs_brotli.json")


# Brotli-friendly content: JSON, HTML, JS, CSS, plain text. Real files only.
INPUTS = [
    r"D:\4\03_literature_data\Deep_learning_zenodo.json",
    r"D:\4\03_literature_data\Supervised_zenodo.json",
    r"D:\4\03_literature_data\Байес_zenodo.json",
    r"D:\4\03_literature_data\Криптография_zenodo.json",
    r"D:\4\03_literature_data\Парсинг_zenodo.json",
    r"D:\4\03_literature_data\Комбинаторика_zenodo.json",
    r"D:\4\03_literature_data\Топология_zenodo.json",
    r"D:\4\03_literature_data\Эволюция_zenodo.json",
]


def brotli_bench(data: bytes, q: int) -> dict:
    t = time.perf_counter()
    c = brotli.compress(data, quality=q)
    pack_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    r = brotli.decompress(c)
    dec_ms = (time.perf_counter() - t) * 1000.0
    assert r == data, f"brotli roundtrip failed at q={q}"
    return {
        "size": len(c),
        "ratio_pct": round(100.0 * len(c) / len(data), 4),
        "pack_ms": round(pack_ms, 2),
        "decode_ms": round(dec_ms, 2),
    }


def bha_bench(paths: list[str]) -> dict:
    """Run bha_cli benchmark and return {path: row}."""
    cmd = [sys.executable, BHA_CLI, "benchmark", "--json", *paths]
    t = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    elapsed = (time.perf_counter() - t) * 1000.0
    if proc.returncode != 0:
        return {"error": proc.stderr, "stdout": proc.stdout, "elapsed_ms": elapsed}
    j = json.loads(proc.stdout)
    return {
        "by_path": {r["path"]: r for r in j["rows"]},
        "total_elapsed_ms": round(elapsed, 2),
    }


def main() -> int:
    # 1. Brotli per file
    brotli_results: dict[str, dict] = {}
    for p in INPUTS:
        pp = Path(p)
        if not pp.exists():
            continue
        data = pp.read_bytes()
        b6 = brotli_bench(data, 6)
        b11 = brotli_bench(data, 11)
        brotli_results[p] = {
            "size_in": len(data),
            "brotli_q6": b6,
            "brotli_q11": b11,
        }
        print(
            f"  {pp.name:50s}  in={len(data):>9d}  "
            f"q6={b6['size']:>8d} ({b6['ratio_pct']:5.2f}%)  "
            f"q11={b11['size']:>8d} ({b11['ratio_pct']:5.2f}%)"
        )

    # 2. BHA per file
    print(f"\n--- BHA benchmark ({len(INPUTS)} files) ---")
    bha_raw = bha_bench(INPUTS)
    if "error" in bha_raw:
        print("BHA failed:", bha_raw["error"])
        return 1

    # 3. Side-by-side
    rows: list[dict] = []
    for p, br in brotli_results.items():
        bha_row = bha_raw["by_path"].get(p, {})
        bha_size = bha_row.get("archive_bytes", -1)
        brotli_q6 = br["brotli_q6"]["size"]
        brotli_q11 = br["brotli_q11"]["size"]
        if bha_size < 0:
            verdict = "n/a"
        elif bha_size < brotli_q11:
            verdict = "BHA"
        elif bha_size < brotli_q6:
            verdict = "BHA<q6 / BHA>=q11"
        else:
            verdict = "brotli"
        rows.append({
            "file": Path(p).name,
            "size_in": br["size_in"],
            "bha_size": bha_size,
            "bha_ratio_pct": bha_row.get("ratio_pct"),
            "bha_pack_ms": bha_row.get("pack_ms"),
            "brotli_q6_size": brotli_q6,
            "brotli_q6_ratio_pct": br["brotli_q6"]["ratio_pct"],
            "brotli_q6_pack_ms": br["brotli_q6"]["pack_ms"],
            "brotli_q11_size": brotli_q11,
            "brotli_q11_ratio_pct": br["brotli_q11"]["ratio_pct"],
            "brotli_q11_pack_ms": br["brotli_q11"]["pack_ms"],
            "verdict": verdict,
            "delta_bha_minus_q11_pct": round(100.0 * (bha_size - brotli_q11) / brotli_q11, 2) if bha_size > 0 else None,
        })

    print(f"\n{'file':50s} {'in':>10s} {'BHA':>10s} {'q6':>10s} {'q11':>10s}  {'BHA%':>6s} {'q6%':>6s} {'q11%':>6s}  verdict")
    for r in rows:
        print(
            f"{r['file']:50s} {r['size_in']:>10d} {r['bha_size']:>10d} "
            f"{r['brotli_q6_size']:>10d} {r['brotli_q11_size']:>10d}  "
            f"{r['bha_ratio_pct']:>6.2f} {r['brotli_q6_ratio_pct']:>6.2f} {r['brotli_q11_ratio_pct']:>6.2f}  {r['verdict']}"
        )

    # 4. Aggregate
    valid = [r for r in rows if r["bha_size"] > 0]
    n_bha_wins = sum(1 for r in valid if r["bha_size"] < r["brotli_q11_size"])
    n_bha_beats_q6 = sum(1 for r in valid if r["bha_size"] < r["brotli_q6_size"])
    bha_total = sum(r["bha_size"] for r in valid)
    q6_total = sum(r["brotli_q6_size"] for r in valid)
    q11_total = sum(r["brotli_q11_size"] for r in valid)
    in_total = sum(r["size_in"] for r in valid)

    summary = {
        "files_compared": len(valid),
        "bha_total_bytes": bha_total,
        "brotli_q6_total_bytes": q6_total,
        "brotli_q11_total_bytes": q11_total,
        "input_total_bytes": in_total,
        "bha_overall_ratio_pct": round(100.0 * bha_total / in_total, 4),
        "brotli_q6_overall_ratio_pct": round(100.0 * q6_total / in_total, 4),
        "brotli_q11_overall_ratio_pct": round(100.0 * q11_total / in_total, 4),
        "bha_wins_vs_q11": n_bha_wins,
        "bha_wins_vs_q6": n_bha_beats_q6,
        "bha_vs_q11_size_delta_pct": round(100.0 * (bha_total - q11_total) / q11_total, 2),
    }
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = {
        "summary": summary,
        "rows": rows,
        "inputs": INPUTS,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
