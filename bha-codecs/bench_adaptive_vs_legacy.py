"""Measure full BHA pipeline (sequential) with adaptive bha_delta
vs the legacy plain-delta bha_delta, on the same fixtures."""
import sys, time, json
from pathlib import Path
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))  # parent of bha_core/
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

import bha_core.bha_delta as bha_delta
import bha_core.bha as bha
import black_hole_archiver

# Snapshot legacy bha_delta._adaptive_encode_int to a baseline
# We just call bha.bha_compress which uses delta_pp internally.
def measure(data, src_path, label):
    t = time.perf_counter()
    arc, _, meta = bha.bha_compress(data, src_path=src_path, total_timeout_s=120)
    dt = time.perf_counter() - t
    return {
        'label': label,
        'in': len(data),
        'out': len(arc),
        'ratio_pct': round(100 * len(arc) / len(data), 3),
        'elapsed_s': round(dt, 2),
        'finished': meta.get('reached_finish'),
    }

# Restore legacy behavior temporarily: replace _adaptive_encode_int with _delta_encode
orig_adaptive = bha_delta._adaptive_encode_int
def legacy_encode(values):
    return bha_delta._delta_encode(values)

fixtures = [
    ('delta_arith_500kb.csv',        r'D:\4\bha-codecs\benchmark\delta_arith_500kb.csv'),
    ('delta_mixed_500kb.csv',        r'D:\4\bha-codecs\benchmark\delta_mixed_500kb.csv'),
    ('delta_quadratic_500kb.csv',    r'D:\4\bha-codecs\benchmark\delta_quadratic_500kb.csv'),
    ('delta_log_per_sec_500kb.csv',  r'D:\4\bha-codecs\benchmark\delta_log_per_sec_500kb.csv'),
    ('delta_status_alternating_500kb.csv', r'D:\4\bha-codecs\benchmark\delta_status_alternating_500kb.csv'),
]

print(f"{'file':40s}  {'in':>9s}  {'legacy_out':>10s}  {'adapt_out':>9s}  {'gain':>8s}  {'time_s':>7s}")
print("-" * 100)

results = []
for name, p in fixtures:
    data = open(p, 'rb').read()

    # Legacy: plain delta (force it by monkey-patching)
    bha_delta._adaptive_encode_int = legacy_encode
    leg = measure(data, Path(p), 'legacy')

    # Adaptive (current)
    bha_delta._adaptive_encode_int = orig_adaptive
    ad = measure(data, Path(p), 'adaptive')

    diff = leg['out'] - ad['out']
    pct = 100 * diff / leg['out']
    print(f"{name:40s}  {len(data):>9d}  {leg['out']:>10d}  {ad['out']:>9d}  "
          f"{pct:+7.2f}%  {ad['elapsed_s']:>6.2f}s")
    results.append({'file': name, **leg, **{'adapt_out': ad['out'], 'gain_pct': pct}})

# Restore
bha_delta._adaptive_encode_int = orig_adaptive

total_in = sum(r['in'] for r in results)
total_legacy = sum(r['out'] for r in results)
total_adapt = sum(r['adapt_out'] for r in results)
print(f"\n{'TOTAL':40s}  {total_in:>9d}  {total_legacy:>10d}  {total_adapt:>9d}  "
      f"{100*(total_legacy-total_adapt)/total_legacy:+7.2f}%")
