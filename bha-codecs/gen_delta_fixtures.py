"""Generate synthetic numeric CSV and telemetry-log fixtures
for the per-column delta encoding benchmark.

Three patterns (per memory L17 - LZMA2 columnar saturation rule):
  A. arithmetic progression:    col[i] = a0 + i*step  (delta is constant)
  B. quadratic:                  col[i] = a0 + i*step + i*i*accel
  C. sparse-random:              col[i] = a0 + i + rand_noise
  D. mixed-types:                mix of A, B, C columns

Each fixture = one column (or multiple) of integers separated by
newlines, plus a header. ~50KB-200KB in size.
"""
import os
import random

OUT = r'D:\\4\\bha-codecs\\benchmark'

def gen_arithmetic(target_kb: int, seed: int, n_cols: int = 1) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // (12 * n_cols)
    parts = [b'idx,']
    parts.append(b','.join(f'c{i}'.encode() for i in range(n_cols)))
    parts.append(b'\n')
    a0 = [rnd.randint(0, 1000) for _ in range(n_cols)]
    step = [rnd.randint(1, 100) for _ in range(n_cols)]
    for i in range(n_rows):
        parts.append(f'{i},'.encode())
        parts.append(b','.join((str(a0[c] + i * step[c])).encode() for c in range(n_cols)))
        parts.append(b'\n')
    return b''.join(parts)


def gen_quadratic(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 20
    a0 = rnd.randint(0, 100)
    v = rnd.randint(1, 50)
    accel = rnd.randint(0, 5)
    parts = [b'idx,val\n']
    for i in range(n_rows):
        parts.append(f'{i},{a0 + i*v + i*i*accel}\n'.encode())
    return b''.join(parts)


def gen_sparse_random(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 16
    parts = [b'idx,val,noise\n']
    for i in range(n_rows):
        v = i + rnd.randint(-3, 3)
        parts.append(f'{i},{v},{rnd.randint(0, 100)}\n'.encode())
    return b''.join(parts)


def gen_mixed(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 30
    a0, step, b0, bstep, c0, cstep = 100, 7, 1000.0, 0.5, 1, 3
    parts = [b'idx,a_int,b_drift,c_small,d_count\n']
    for i in range(n_rows):
        a = a0 + i * step
        b = int(b0 + bstep * i)
        c = c0 + (i % 5) * cstep
        d = rnd.randint(0, 100)
        parts.append(f'{i},{a},{b},{c},{d}\n'.encode())
    return b''.join(parts)


# Generate fixtures: 50KB, 100KB, 200KB, 500KB - 4 sizes x 4 patterns = 16 files
PATTERNS = [
    ('arith', gen_arithmetic),
    ('quadratic', gen_quadratic),
    ('sparse_random', gen_sparse_random),
    ('mixed', gen_mixed),
]
SIZES_KB = [50, 100, 200, 500]
SEEDS = {
    'arith': 1, 'quadratic': 2, 'sparse_random': 3, 'mixed': 4,
}
for name, fn in PATTERNS:
    for kb in SIZES_KB:
        p = os.path.join(OUT, f'delta_{name}_{kb}kb.csv')
        data = fn(kb, SEEDS[name])
        with open(p, 'wb') as f:
            f.write(data)
        print(f'  wrote {p} ({len(data)} B)')
print('done')
