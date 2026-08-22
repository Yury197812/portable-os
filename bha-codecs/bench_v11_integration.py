"""Bench v11 vs no-v11 in bha_parallel.

Measures how often the v11-prioritized gate list produces a BETTER result
than the unprioritized full list, by running both and comparing winners.

Usage:
  python bench_v11_integration.py
"""
import os, sys, time, json
from pathlib import Path
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))  # parent of bha_core/
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

# Disable v11 first
os.environ['BHA_USE_V11'] = '0'
import importlib
import bha_core.bha_parallel as bp0
importlib.reload(bp0)

# Enable v11
os.environ['BHA_USE_V11'] = '1'
import bha_core.bha_parallel as bp1
importlib.reload(bp1)

CORPUS = Path(r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST')
files = sorted([p for p in CORPUS.iterdir() if p.is_file() and p.suffix != ".json" and p.stat().st_size > 500_000])
print(f'files to test (>=500KB): {len(files)}')

# Skip brotli-only runs to save time; just measure gate-list difference.
import bha_core.bha as bha_seq

wins_v11 = wins_nov11 = ties = 0
results = []
for fi, fp in enumerate(files, 1):
    data = fp.read_bytes()
    t0 = time.perf_counter()
    seq_arc, _, seq_meta = bha_seq.bha_compress(data, src_path=fp, total_timeout_s=60)
    seq_ms = (time.perf_counter() - t0) * 1000

    # Without v11 (env var doesn't reload — call direct paths)
    t0 = time.perf_counter()
    par_arc0, par_meta0 = bp0.bha_parallel_compress(data, src_path=fp, baseline=seq_arc)
    par0_ms = (time.perf_counter() - t0) * 1000

    # With v11
    t0 = time.perf_counter()
    par_arc1, par_meta1 = bp1.bha_parallel_compress(data, src_path=fp, baseline=seq_arc)
    par1_ms = (time.perf_counter() - t0) * 1000

    diff = len(par_arc1) - len(par_arc0)
    if len(par_arc1) < len(par_arc0):
        wins_v11 += 1
        verdict = 'v11_better'
    elif len(par_arc1) > len(par_arc0):
        wins_nov11 += 1
        verdict = 'nov11_better'
    else:
        ties += 1
        verdict = 'tie'

    print(f'  [{fi}/{len(files)}] {fp.name[:35]:35s}  '
          f'seq={len(seq_arc):>6d}  nov11={len(par_arc0):>6d}  '
          f'v11={len(par_arc1):>6d}  diff={diff:+d}  {verdict}')

    results.append({
        'file': fp.name,
        'input_size': len(data),
        'seq_size': len(seq_arc),
        'nov11_size': len(par_arc0),
        'v11_size': len(par_arc1),
        'diff': diff,
        'verdict': verdict,
        'v11_priority': par_meta1.get('v11_priority'),
        'v11_lzma_preset': par_meta1.get('v11_lzma_preset'),
    })

# Save
out_dir = Path(r'D:\4\bha-codecs\benchmark\v11-integration')
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / 'results.json'
out.write_text(json.dumps({
    'description': 'Compare bha_parallel with and without v11 recommender on BHA corpus',
    'n_files': len(files),
    'wins_v11': wins_v11,
    'wins_nov11': wins_nov11,
    'ties': ties,
    'rows': results,
}, indent=2))
print(f'\nresults: {out}')
print(f'wins_v11={wins_v11}  wins_nov11={wins_nov11}  ties={ties}')