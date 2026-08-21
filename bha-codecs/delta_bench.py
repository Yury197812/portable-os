"""
Generate benchmark report: bha + delta_pp on 16 delta fixtures.
Output: benchmark/delta_results.json
"""
import os
import json
import sys
import time

sys.path.insert(0, r'D:\\4\\bha-codecs')
import lzma
import bha

# Run bha_compress on each delta fixture
results = []
bench = r'D:\\4\\bha-codecs\\benchmark'
for f in sorted(os.listdir(bench)):
    if not f.startswith('delta_') or not f.endswith('.csv'):
        continue
    p = os.path.join(bench, f)
    data = open(p, 'rb').read()
    in_size = len(data)
    # Run 3 times for determinism check
    sizes = []
    elapsed_ms = []
    for _ in range(3):
        t0 = time.perf_counter()
        inner, stats, meta = bha.bha_compress(data, total_timeout_s=60.0)
        elapsed_ms.append((time.perf_counter() - t0) * 1000)
        if meta['reached_finish']:
            sizes.append(len(inner))
    if not sizes:
        continue
    median_size = sorted(sizes)[len(sizes) // 2]
    delta_used = stats == ('delta_pp', ...) or (isinstance(stats, tuple) and stats[0] == 'delta_pp')
    # also raw lzma for comparison
    raw_lzma = len(lzma.compress(data, format=lzma.FORMAT_XZ, preset=6))
    results.append({
        'file': f,
        'input_bytes': in_size,
        'bha_size': median_size,
        'bha_ratio_pct': round(100 * median_size / in_size, 4),
        'bha_delta_used': delta_used,
        'raw_lzma_size': raw_lzma,
        'raw_lzma_ratio_pct': round(100 * raw_lzma / in_size, 4),
        'pack_ms_median': round(sorted(elapsed_ms)[len(elapsed_ms) // 2], 1),
    })

out = r'D:\\4\\bha-codecs\\benchmark\delta_results.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'wrote {out} ({len(results)} rows)')
for r in results:
    gain_vs_raw = 100 * (r['raw_lzma_size'] - r['bha_size']) / r['raw_lzma_size']
    print(f'  {r["file"]:35s}  in={r["input_bytes"]:>7d}  raw_lzma={r["raw_lzma_size"]:>6d}  bha={r["bha_size"]:>6d}  gain={gain_vs_raw:+.1f}%')
