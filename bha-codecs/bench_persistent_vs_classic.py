"""Compare bha_parallel (per-call pool) vs bha_persistent_pool (long-lived).

Reproduces the 6-fixture benchmark from bha-codecs/README.md section 11.4,
then re-runs the same fixtures with the persistent pool to measure the
speedup gain from amortizing worker startup.

Outputs:
  - stdout: per-file size + time + best_gate + speedup
  - benchmark/persistent-vs-classic.json: machine-readable summary
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))  # parent of bha_core/
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

import bha_core.bha as bha  # baseline sequential
import bha_core.bha_parallel as bp_classic
import bha_core.bha_persistent_pool as bp_persistent
import black_hole_archiver  # ensure runtime loaded

FIXTURES = [
    ("delta_arith_500kb.csv",       "D:\\4\\bha-codecs\\benchmark\\delta_arith_500kb.csv"),
    ("delta_mixed_500kb.csv",       "D:\\4\\bha-codecs\\benchmark\\delta_mixed_500kb.csv"),
    ("delta_log_per_sec_500kb.csv", "D:\\4\\bha-codecs\\benchmark\\delta_log_per_sec_500kb.csv"),
    ("delta_status_alternating_500kb.csv", "D:\\4\\bha-codecs\\benchmark\\delta_status_alternating_500kb.csv"),
    # HTML fixtures from BHA TEST corpus
    ("html_500k", "D:\\PROJECT UNIVERSE\\01Compression\\BHA\\TEST\\html_inline_data_uri_200k.html"),
    ("bro_html_500k", "D:\\PROJECT UNIVERSE\\01Compression\\BHA\\TEST\\css_repeated_150k.css"),
]


def time_call(fn, *args, **kwargs):
    t = time.perf_counter()
    result = fn(*args, **kwargs)
    return (time.perf_counter() - t) * 1000.0, result


def main():
    rows = []
    print(f"{'file':40s}  {'in':>9s}  {'classic_par_ms':>14s}  {'persistent_1st_ms':>16s}  {'persistent_2nd_ms':>16s}  {'speedup':>8s}  {'best_gate':>12s}")
    print("-" * 130)

    # We need a baseline (sequential bha_compress) for the comparison
    # to be meaningful — that's what callers usually provide.
    for name, path_str in FIXTURES:
        path = Path(path_str)
        if not path.exists():
            print(f"SKIP {name}: not found at {path_str}")
            continue
        data = path.read_bytes()

        # 1. Baseline (sequential bha_compress) — feeds both pools
        try:
            seq_ms, (seq_arc, _stats, seq_meta) = time_call(
                bha.bha_compress, data, src_path=path, total_timeout_s=120.0
            )
        except Exception as e:
            print(f"FAIL {name}: baseline error {e}")
            continue
        if not seq_meta["reached_finish"]:
            print(f"FAIL {name}: baseline timed out")
            continue

        # 2. Classic parallel (per-call pool)
        try:
            classic_ms, (classic_arc, classic_meta) = time_call(
                bp_classic.bha_parallel_compress,
                data, src_path=path, baseline=seq_arc
            )
        except Exception as e:
            print(f"FAIL {name}: classic parallel error {e}")
            classic_ms = float('nan')
            classic_arc = b''
            classic_meta = {"best_gate": "error"}

        # 3. Persistent parallel, 1st call (cold pool — pays spawn cost)
        try:
            p1_ms, (p1_arc, p1_meta) = time_call(
                bp_persistent.bha_parallel_compress,
                data, src_path=path, baseline=seq_arc
            )
        except Exception as e:
            print(f"FAIL {name}: persistent 1st error {e}")
            p1_ms = float('nan')
            p1_arc = b''
            p1_meta = {"best_gate": "error"}

        # 4. Persistent parallel, 2nd call (warm pool)
        try:
            p2_ms, (p2_arc, p2_meta) = time_call(
                bp_persistent.bha_parallel_compress,
                data, src_path=path, baseline=seq_arc
            )
        except Exception as e:
            print(f"FAIL {name}: persistent 2nd error {e}")
            p2_ms = float('nan')
            p2_arc = b''
            p2_meta = {"best_gate": "error"}

        # Speedup: persistent 2nd vs classic
        if classic_ms > 0 and p2_ms > 0:
            speedup = classic_ms / p2_ms
        else:
            speedup = float('nan')

        rows.append({
            "file": name,
            "path": path_str,
            "input_bytes": len(data),
            "baseline_size": len(seq_arc),
            "baseline_ms": round(seq_ms, 1),
            "classic_par_size": len(classic_arc),
            "classic_par_ms": round(classic_ms, 1),
            "classic_best": classic_meta.get("best_gate"),
            "persistent_1st_size": len(p1_arc),
            "persistent_1st_ms": round(p1_ms, 1),
            "persistent_1st_init_ms": p1_meta.get("pool_init_ms"),
            "persistent_2nd_size": len(p2_arc),
            "persistent_2nd_ms": round(p2_ms, 1),
            "persistent_2nd_init_ms": p2_meta.get("pool_init_ms"),
            "speedup_persistent2nd_vs_classic": round(speedup, 3),
        })

        print(
            f"{name:40s}  {len(data):>9d}  "
            f"{classic_ms:>14.0f}  {p1_ms:>16.0f}  {p2_ms:>16.0f}  "
            f"{speedup:>7.2f}x  "
            f"{p2_meta.get('best_gate', '?'):>12s}"
        )

    # Shutdown persistent pool
    bp_persistent.shutdown_pool()

    # Write JSON summary
    out_dir = Path(r"D:\4\bha-codecs\benchmark\persistent-vs-classic")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.json"
    out_path.write_text(json.dumps({
        "description": "Classic per-call ProcessPoolExecutor vs persistent long-lived pool",
        "n_fixtures": len(rows),
        "rows": rows,
    }, indent=2))
    print(f"\nresults: {out_path}")

    # Aggregate stats
    valid = [r for r in rows if r["speedup_persistent2nd_vs_classic"] == r["speedup_persistent2nd_vs_classic"]]
    if valid:
        avg_speedup = sum(r["speedup_persistent2nd_vs_classic"] for r in valid) / len(valid)
        wins = sum(1 for r in valid if r["speedup_persistent2nd_vs_classic"] > 1.0)
        print(f"\navg speedup: {avg_speedup:.2f}x  wins: {wins}/{len(valid)}")


if __name__ == "__main__":
    main()
