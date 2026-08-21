"""Quick rebuild on remaining files (10k each).
Skips bro_specific_html_500k (already 500 done) and bro_html+json-80k (5000 done).
Just runs JSON-80k and Markdown-80k at 10k, then merges into the existing JSON.
"""
import json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import bha
from black_hole_archiver import pack_file, unpack_archive, _sha256_file

OUT = Path(r"D:\4\bha-codecs\benchmark\rebuild_10k.json")
existing = json.loads(OUT.read_text()) if OUT.exists() else {"files": {}}

CASES = [
    (r"D:\4\bha-codecs\benchmark\bro_json-80k.json", 10000),
    (r"D:\4\bha-codecs\benchmark\bro_markdown-80k.md", 5000),  # slower
]

for path, n in CASES:
    p = Path(path)
    if not p.exists():
        print(f"skip {p.name}: missing"); continue
    if p.name in existing["files"]:
        print(f"skip {p.name}: already done"); continue
    data = p.read_bytes()
    sha = _sha256_file(p)
    sizes, pack_ms = [], []
    rt_fails = 0
    t0 = time.perf_counter()
    print(f"\n=== {p.name}  in={len(data):>10d}  n={n} ===", flush=True)
    for i in range(n):
        t = time.perf_counter()
        out, _, dst = pack_file(p, None)
        pm = 1000*(time.perf_counter()-t)
        try:
            d = unpack_archive(out)
            if _sha256_file(d) != sha: rt_fails += 1
        except Exception:
            rt_fails += 1
        try: out.unlink()
        except OSError: pass
        sizes.append(dst); pack_ms.append(pm)
        if (i+1) % 1000 == 0:
            print(f"  [{i+1}/{n}] elapsed={time.perf_counter()-t0:.0f}s  "
                  f"last_ms={pm:.0f}  rt_fails={rt_fails}", flush=True)
    elapsed = time.perf_counter()-t0
    existing["files"][p.name] = {
        "file": p.name, "input_bytes": len(data), "n": n,
        "elapsed_s": round(elapsed, 2),
        "throughput_files_per_s": round(n/elapsed, 2),
        "size_bytes": {
            "min": min(sizes), "max": max(sizes),
            "median": int(statistics.median(sizes)),
            "mean": round(statistics.mean(sizes), 1),
            "stdev": round(statistics.stdev(sizes), 2) if len(sizes)>1 else 0,
            "unique_count": len(set(sizes)),
        },
        "ratio_pct_median": round(100*statistics.median(sizes)/len(data), 4),
        "pack_ms": {
            "min": round(min(pack_ms), 2),
            "p50": round(statistics.median(pack_ms), 2),
            "p95": round(sorted(pack_ms)[int(0.95*len(pack_ms))], 2),
            "p99": round(sorted(pack_ms)[int(0.99*len(pack_ms))], 2),
            "max": round(max(pack_ms), 2),
            "mean": round(statistics.mean(pack_ms), 2),
        },
        "rt_fails": rt_fails,
        "rt_pass_rate_pct": round(100*(n-rt_fails)/n, 4),
    }
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    print(f"  >>> {p.name}: {n} in {elapsed:.0f}s  median={existing['files'][p.name]['pack_ms']['p50']:.1f}ms  "
          f"p99={existing['files'][p.name]['pack_ms']['p99']:.1f}ms  size_unique={len(set(sizes))}  rt_fails={rt_fails}")

print(f"\nDONE -> {OUT}")
