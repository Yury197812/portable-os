"""Generate float-heavy CSV fixtures for adaptive-scale delta benchmark.

Three patterns:
  A. low-delta floats:    val = 100.0 + i*0.001  (sub-nano scale needed)
  B. mid-delta floats:    val = 100.0 + i*0.5    (milli scale)
  C. high-delta floats:   val = 100.0 + i*50.0   (integer scale)
  D. wide-range floats:   val = 100.0 + i*1e6    (force scale=1)
"""
import os
import random

OUT = r'D:\\4\\bha-codecs\\benchmark'

def gen_float_low(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 18
    parts = [b'idx,val\n']
    for i in range(n_rows):
        parts.append(f'{i},{100.0 + i*0.001 + rnd.uniform(-0.0001, 0.0001):.6f}\n'.encode())
    return b''.join(parts)


def gen_float_mid(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 16
    parts = [b'idx,val\n']
    for i in range(n_rows):
        parts.append(f'{i},{100.0 + i*0.5 + rnd.uniform(-0.1, 0.1):.3f}\n'.encode())
    return b''.join(parts)


def gen_float_high(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 14
    parts = [b'idx,val\n']
    for i in range(n_rows):
        parts.append(f'{i},{100.0 + i*50.0 + rnd.uniform(-10, 10):.1f}\n'.encode())
    return b''.join(parts)


def gen_float_wide(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 22
    parts = [b'idx,val\n']
    for i in range(n_rows):
        # monotonic growth with capped step (forces scale=1)
        step = min(1e6, 1e6 * (1.0 + i / 100.0))
        parts.append(f'{i},{i*step + rnd.uniform(0, step):.6e}\n'.encode())
    return b''.join(parts)


PATTERNS = [
    ('float_low', gen_float_low),
    ('float_mid', gen_float_mid),
    ('float_high', gen_float_high),
    ('float_wide', gen_float_wide),
]
SIZES_KB = [50, 100, 200, 500]
SEEDS = {'float_low': 5, 'float_mid': 6, 'float_high': 7, 'float_wide': 8}
for name, fn in PATTERNS:
    for kb in SIZES_KB:
        p = os.path.join(OUT, f'delta_{name}_{kb}kb.csv')
        data = fn(kb, SEEDS[name])
        with open(p, 'wb') as f:
            f.write(data)
        print(f'  wrote {p} ({len(data)} B)')
print('done')
