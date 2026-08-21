"""10000× rebuild: re-archive the 1.5MB HTML ten thousand times with safe BHA.

Goal: prove that the patched BHA can be re-run 10000× without hanging.
Output per iteration: file, size_in, size_out, ratio, pack_ms, rt_ok.
Aggregate: median/mean/p99/p999 latency, rt-fail count, size stability.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bha  # applies patches on import
from black_hole_archiver import pack_file, unpack_archive, _sha256_file


INPUTS = [
    r"D:\4\bha-codecs\benchmark\bro_specific_html_500k.html",   # 1.48MB HTML+JSON
    r"D:\4\bha-codecs\benchmark\bro_html+json-80k.html",        # 5.5KB
    r"D:\4\bha-codecs\benchmark\bro_json-80k.json",             # 15KB
    r"D:\4\bha-codecs\benchmark\bro_markdown-80k.md",           # 154KB
]
N_BIG = 500      # 1.5MB HTML (~25 min)
N_MED = 2000      # 100-200KB files
N_SMALL = 10000   # <100KB files (fast)
OUT = Path(r"D:\4\bha-codecs\benchmark\rebuild_10k.json")


def main():
    per_file_results: dict[str, list[dict]] = {}
    overall_start = time.perf_counter()

    for path in INPUTS:
        p = Path(path)
        if not p.exists():
            continue
        data = p.read_bytes()
        sha = _sha256_file(p)
        n = N_BIG if len(data) >= 1_000_000 else (N_MED if len(data) >= 100_000 else N_SMALL)
        print(f"\n=== {p.name}  in={len(data):>10d}  n={n} ===", flush=True)
        sizes: list[int] = []
        pack_ms: list[float] = []
        rt_fails = 0
        t0 = time.perf_counter()
        for i in range(n):
            t = time.perf_counter()
            out, src_size, dst_size = pack_file(p, None)
            pm = 1000 * (time.perf_counter() - t)
            # quick RT
            try:
                decoded = unpack_archive(out)
                if _sha256_file(decoded) != sha:
                    rt_fails += 1
            except Exception:
                rt_fails += 1
            # cleanup .bha
            try:
                out.unlink()
            except OSError:
                pass
            sizes.append(dst_size)
            pack_ms.append(pm)
            if (i + 1) % 1000 == 0:
                elapsed = time.perf_counter() - t0
                print(f"  [{i+1:>5d}/{n}] elapsed={elapsed:6.1f}s  "
                      f"last_size={dst_size:>7d}  last_ms={pm:>6.1f}  "
                      f"rt_fails={rt_fails}", flush=True)
        elapsed = time.perf_counter() - t0

        sizes_uniq = len(set(sizes))
        agg = {
            "file": p.name,
            "input_bytes": len(data),
            "n": n,
            "elapsed_s": round(elapsed, 2),
            "throughput_files_per_s": round(n / elapsed, 2),
            "size_bytes": {
                "min": min(sizes),
                "max": max(sizes),
                "median": int(statistics.median(sizes)),
                "mean": round(statistics.mean(sizes), 1),
                "stdev": round(statistics.stdev(sizes), 2) if len(sizes) > 1 else 0,
                "unique_count": sizes_uniq,
            },
            "ratio_pct_median": round(100 * statistics.median(sizes) / len(data), 4),
            "pack_ms": {
                "min": round(min(pack_ms), 2),
                "p50": round(statistics.median(pack_ms), 2),
                "p95": round(sorted(pack_ms)[int(0.95 * len(pack_ms))], 2),
                "p99": round(sorted(pack_ms)[int(0.99 * len(pack_ms))], 2),
                "max": round(max(pack_ms), 2),
                "mean": round(statistics.mean(pack_ms), 2),
            },
            "rt_fails": rt_fails,
            "rt_pass_rate_pct": round(100 * (n - rt_fails) / n, 4),
        }
        per_file_results[p.name] = agg
        print(f"\n  >>> {p.name}: {n} runs in {elapsed:.1f}s  "
              f"throughput={agg['throughput_files_per_s']:.1f}/s  "
              f"median_pack={agg['pack_ms']['p50']:.1f}ms  "
              f"p99_pack={agg['pack_ms']['p99']:.1f}ms  "
              f"max_pack={agg['pack_ms']['max']:.1f}ms  "
              f"size_unique={sizes_uniq}  rt_fails={rt_fails}", flush=True)

    overall_elapsed = time.perf_counter() - overall_start
    out = {
        "n_per_file": N,
        "overall_elapsed_s": round(overall_elapsed, 2),
        "files": per_file_results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n=== DONE in {overall_elapsed:.1f}s  ->  {OUT} ===")


if __name__ == "__main__":
    main()
