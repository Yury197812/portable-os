"""bench_v11_brotli_vs_bha: validate T1 gains on the real BHA_VS_BROTLI corpus.

What we measure per file:
  - Plain BHA pipeline (sequential bha_compress via bha.py --bench).
  - v11 + parallel (bha_parallel_compress with BHA_USE_V11=1).
  - Brotli q11 directly (sanity reference: best-case for <=64KB web).

We don't run the BHA runtime here (would need PYTHONPATH setup); we
exercise v11 + worker_gate to show brotli is correctly prioritised
and reaches the smallest output for the in-domain cases.

Output:
  benchmark/v11-brotli-vs-bha/results.json
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))  # D:\4\bha-codecs

from bha_core import bha_recommender_v11, bha_codec_backends, bha_parallel


# Real BHA_VS_BROTLI small-file fixtures. Cap at <=64 KB to stay in
# the brotli crossover window (T1 routing zone).
CANDIDATES = [
    'bro_html+json-50k.html',
    'bro_json-50k.json',
    'bro_json-80k.json',
    'bro_markdown-50k.md',
    'bro_markdown-80k.md',
    'crossover_html_100kb.html',
    'crossover_json_100kb.json',
]

ROOT = _HERE  # benchmark dir
RESULTS_PATH = ROOT / 'v11-brotli-vs-bha' / 'results.json'


def _resolve(name: str) -> Path | None:
    """Find the canonical fixture (skip numbered iter artefacts).

    The benchmark directory contains thousands of auto-generated files
    like 'bro_html+json-80k (1).html' ... '(10000).html' from the
    16200-iteration determinism check in BHA_SAFE_SKILLS SKILL 5.
    We exclude anything containing `(N)` suffix so we test on originals.
    """
    import re
    pattern = re.compile(r'\(\d+\)')
    for cand in sorted(ROOT.glob(name)):
        if cand.is_file() and not pattern.search(cand.name):
            return cand
    # Fallback: any match, even numbered
    matches = sorted(ROOT.glob(name))
    return matches[0] if matches else None


def measure_file(path: Path) -> dict:
    data = path.read_bytes()
    size = len(data)
    name = path.name

    # 1. v11 recommendation for this file
    rec = bha_recommender_v11.recommend(name, size, k=5)

    # 2. Direct brotli q11 / q6 sizes (lower bound)
    brotli_q11_size = len(bha_codec_backends.brotli_compress(data, quality=11))
    brotli_q6_size = len(bha_codec_backends.brotli_compress(data, quality=6))

    # 3. LZMA reference (what lzma_fallback would produce)
    import lzma
    lzma_size = len(lzma.compress(data, format=lzma.FORMAT_XZ, preset=6))

    # 4. Worker_gate via stubbed ssp - runs brotli directly
    bp = bha_parallel
    bp._WORKER_SSP = type('StubS', (), {})()
    t0 = time.perf_counter()
    res_brotli = bp.worker_gate(('brotli_q11', data, str(path)))
    t_brotli = (time.perf_counter() - t0) * 1000

    # Worker_gate for lzma_fallback needs BHA runtime (black_hole_archiver).
    # Skip if not importable, just record LZMA reference above.
    lzma_via_gate = None
    try:
        sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')
        from black_hole_archiver import _build_file_lzma_fallback_archive
        lzma_via_gate = len(_build_file_lzma_fallback_archive(data))
    except Exception:
        pass

    return {
        'file': name,
        'size': size,
        'v11_priority_top3': rec[:3],
        'v11_routed_to_brotli_first': rec[0] == 'brotli_q11',
        'brotli_q11_bytes': brotli_q11_size,
        'brotli_q6_bytes': brotli_q6_size,
        'lzma6_xz_bytes': lzma_size,
        'lzma_bha_bytes': lzma_via_gate,
        'brotli_q11_pack_ms': round(t_brotli, 3),
        'brotli_q11_ratio': round(brotli_q11_size / size, 4),
        'brotli_q11_vs_lzma_pct': round(
            100.0 * (brotli_q11_size - lzma_size) / lzma_size, 1
        ) if lzma_size else None,
    }


def main():
    if not bha_codec_backends.is_available():
        print('brotli NOT available, aborting')
        sys.exit(1)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for cand in CANDIDATES:
        path = _resolve(cand)
        if path is None:
            print(f'  SKIP {cand}: no fixture <=128KB')
            continue
        m = measure_file(path)
        results.append(m)
        print(f"  {m['file']:35s}  size={m['size']:>7d}  "
              f"rec={m['v11_priority_top3']}  "
              f"brotli={m['brotli_q11_bytes']:>6d}  "
              f"lzma={m['lzma6_xz_bytes']:>6d}  "
              f"({m['brotli_q11_vs_lzma_pct']:+.1f}% vs lzma)")

    # Aggregate
    n = len(results)
    if n == 0:
        print('no fixtures resolved, aborting')
        sys.exit(1)
    routed_correctly = sum(1 for r in results if r['v11_routed_to_brotli_first'])
    brotli_wins = sum(
        1 for r in results
        if r['brotli_q11_bytes'] < r['lzma6_xz_bytes']
    )
    avg_pct = sum(r['brotli_q11_vs_lzma_pct'] for r in results
                  if r['brotli_q11_vs_lzma_pct'] is not None) / n

    summary = {
        'n_files': n,
        'files': [r['file'] for r in results],
        'v11_routed_brotli_first_count': routed_correctly,
        'brotli_beats_lzma_count': brotli_wins,
        'avg_brotli_vs_lzma_pct': round(avg_pct, 2),
        'note': 'negative pct = brotli smaller than LZMA (i.e. brotli wins)',
    }
    print()
    print(f'  {n} files tested')
    print(f'  v11 routed brotli_q11 first: {routed_correctly}/{n}')
    print(f'  brotli_q11 beats LZMA6:      {brotli_wins}/{n}')
    print(f'  avg brotli vs LZMA:          {avg_pct:+.2f}%')

    out = {'summary': summary, 'per_file': results}
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f'\nResults written to {RESULTS_PATH}')


if __name__ == '__main__':
    main()