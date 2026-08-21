"""Crossover benchmark: BHA vs brotli on 100KB-1MB HTML+JSON.
Generates JSON output suitable for plotting and decision.
"""
import os
import sys
import json
import time

sys.path.insert(0, r'D:\\4\\bha-codecs')
import bha  # applies patches
from black_hole_archiver import _sha256_file
import brotli

OUT = r'D:\\4\\bha-codecs\\benchmark\\crossover_results.json'
SIZES = [100, 200, 400, 800, 1024]
TYPES = ['html', 'json']

results = []
for t in TYPES:
    for kb in SIZES:
        path = f'D:\\4\\bha-codecs\\benchmark\\crossover_{t}_{kb}kb.{t}'
        if not os.path.exists(path):
            print(f'SKIP {path} (not exist)')
            continue
        data = open(path, 'rb').read()
        in_size = len(data)
        # brotli q6/q9/q11
        t0 = time.perf_counter()
        c_q6 = brotli.compress(data, quality=6)
        t_q6 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        c_q9 = brotli.compress(data, quality=9)
        t_q9 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        c_q11 = brotli.compress(data, quality=11)
        t_q11 = (time.perf_counter() - t0) * 1000
        # BHA via bha.bha_compress
        t0 = time.perf_counter()
        inner, _stats, meta = bha.bha_compress(data, total_timeout_s=60.0)
        t_bha = (time.perf_counter() - t0) * 1000
        bha_size = len(inner) if meta['reached_finish'] else -1
        # LZMA preset=6 baseline
        import lzma
        t0 = time.perf_counter()
        c_lzma = lzma.compress(data, format=lzma.FORMAT_XZ, preset=6)
        t_lzma = (time.perf_counter() - t0) * 1000

        row = {
            'file': os.path.basename(path),
            'type': t,
            'kb': kb,
            'in': in_size,
            'brotli_q6': {'size': len(c_q6), 'ms': round(t_q6, 1),
                            'ratio_pct': round(100*len(c_q6)/in_size, 3)},
            'brotli_q9': {'size': len(c_q9), 'ms': round(t_q9, 1),
                            'ratio_pct': round(100*len(c_q9)/in_size, 3)},
            'brotli_q11': {'size': len(c_q11), 'ms': round(t_q11, 1),
                             'ratio_pct': round(100*len(c_q11)/in_size, 3)},
            'bha': {'size': bha_size, 'ms': round(t_bha, 1),
                    'ratio_pct': round(100*bha_size/in_size, 3) if bha_size>0 else None,
                    'reached_finish': meta['reached_finish']},
            'lzma_p6': {'size': len(c_lzma), 'ms': round(t_lzma, 1),
                        'ratio_pct': round(100*len(c_lzma)/in_size, 3)},
        }
        results.append(row)
        verdict = 'BHA' if (bha_size > 0 and bha_size < len(c_q11)) else 'brotli-q11'
        print(f'  {t} {kb}kb: in={in_size}  '
              f'brotli-q11={len(c_q11)} ({row["brotli_q11"]["ratio_pct"]}%, {t_q11:.0f}ms)  '
              f'BHA={bha_size} ({row["bha"]["ratio_pct"]}%, {t_bha:.0f}ms)  '
              f'-> {verdict}')

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nwrote {OUT}')
