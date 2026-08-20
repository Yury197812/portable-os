"""BHA 1M rebuilds benchmark — uses bha-archive skill for archive/extract
on BHA TEST/ corpus files, finds MAX compression.

Each rebuild = 1 archive + 1 extract round-trip.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
BHA_OUT = Path(r"D:\4\bha-codecs\benchmark\1M-output")
BHA_OUT.mkdir(parents=True, exist_ok=True)
SKILL = Path(r"C:\Users\Art\.mimicode\skills\bha-archive\scripts\bha_run.py")


def run_bha(action: str, source: str, output: str = "", timeout: int = 60) -> dict:
    payload = {"action": action, "source": source, "timeout": timeout}
    if output:
        payload["output"] = output
    proc = subprocess.run(
        [sys.executable, str(SKILL)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout + 10,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": "skill_returned_nonzero", "stdout": proc.stdout, "stderr": proc.stderr}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "skill_returned_non_json", "stdout": proc.stdout}


def file_rounds(file_path: Path, rounds: int) -> dict:
    """Run rounds=N archive+extract cycles on a single file."""
    sizes = []
    archive_ms = []
    extract_ms = []
    out_path = BHA_OUT / f"{file_path.name}.bha"
    extract_path = BHA_OUT / f"{file_path.name}.extracted"
    for r in range(rounds):
        result = run_bha("archive", str(file_path), str(out_path))
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "archive_failed")}
        sizes.append(out_path.stat().st_size if out_path.exists() else 0)
        archive_ms.append(result.get("elapsed_ms", 0))
        result = run_bha("extract", str(out_path))
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "extract_failed")}
        extract_ms.append(result.get("elapsed_ms", 0))
    if not sizes:
        return {"ok": False, "error": "no_rounds"}
    return {
        "ok": True,
        "rounds": len(sizes),
        "original_size": file_path.stat().st_size,
        "bha_size_min": min(sizes),
        "bha_size_max": max(sizes),
        "bha_size_mean": round(statistics.mean(sizes)),
        "ratio_min_pct": round(min(sizes) / file_path.stat().st_size * 100, 3),
        "ratio_mean_pct": round(statistics.mean(sizes) / file_path.stat().st_size * 100, 3),
        "archive_ms_mean": round(statistics.mean(archive_ms), 1),
        "extract_ms_mean": round(statistics.mean(extract_ms), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=20000)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    files = sorted([p for p in CORPUS.glob("*") if p.is_file() and p.name != "manifest.json"])
    print(f"corpus: {len(files)} files")
    print(f"rounds per file: {args.rounds:,}")
    print(f"total rebuilds: {len(files) * args.rounds:,}")
    results = {}
    t0 = time.perf_counter()
    for i, f in enumerate(files, 1):
        r = file_rounds(f, args.rounds)
        if not r.get("ok"):
            print(f"  [{i:>2d}/{len(files)}] {f.name}: FAIL ({r.get('error')})")
            continue
        results[f.name] = r
        print(
            f"  [{i:>2d}/{len(files)}] {f.name:40s} "
            f"{r['original_size']:>10d} -> {r['bha_size_mean']:>8d} "
            f"({r['ratio_mean_pct']:.2f}%) "
            f"arch={r['archive_ms_mean']:.1f}ms ext={r['extract_ms_mean']:.1f}ms"
        )
    elapsed = time.perf_counter() - t0
    print(f"\ntotal: {len(results)} files, {len(files) * args.rounds:,} rebuilds in {elapsed:.1f}s")
    print(f"rebuilds/sec: {len(files) * args.rounds / elapsed:.0f}")
    if results:
        avg_ratio = statistics.mean(r["ratio_mean_pct"] for r in results.values())
        print(f"average ratio: {avg_ratio:.3f}%")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "rounds": args.rounds,
                "elapsed_seconds": round(elapsed, 1),
                "results": results,
            }, f, indent=2)
        print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
