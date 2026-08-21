"""Generate boolean-heavy CSV fixtures for delta preprocessor
benchmark. Two patterns:
  - status_all_200: column is always '200' (constant value)
  - status_alternating: 200, 404, 500 in repeating cycles
  - status_bursty: long runs of same status with occasional flips
  - is_error_true_dominant: 90% true, 10% false
  - status_random: random 200/404/500 with stable distribution
"""
import os
import random

OUT = r'D:\\4\\bha-codecs\\benchmark'


def gen_constant(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 6
    parts = [b'request_id,status,method\n']
    for i in range(n_rows):
        parts.append(f'{i},200,GET\n'.encode())
    return b''.join(parts)


def gen_alternating(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 8
    cycle = ['200', '200', '404', '200', '500']
    parts = [b'request_id,status,is_error\n']
    for i in range(n_rows):
        s = cycle[i % len(cycle)]
        is_err = 'true' if s in ('404', '500') else 'false'
        parts.append(f'{i},{s},{is_err}\n'.encode())
    return b''.join(parts)


def gen_bursty(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 7
    parts = [b'idx,status,is_error\n']
    cur = '200'
    for i in range(n_rows):
        # runs of 50-500 of same value
        if i % 73 == 0:
            cur = rnd.choice(['200', '200', '200', '404', '500'])
        is_err = 'true' if cur in ('404', '500') else 'false'
        parts.append(f'{i},{cur},{is_err}\n'.encode())
    return b''.join(parts)


def gen_error_dominant(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 9
    parts = [b'idx,is_error,is_admin\n']
    for i in range(n_rows):
        is_err = 'true' if rnd.random() < 0.9 else 'false'
        is_admin = 'true' if rnd.random() < 0.1 else 'false'
        parts.append(f'{i},{is_err},{is_admin}\n'.encode())
    return b''.join(parts)


def gen_random_dist(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 8
    parts = [b'idx,level,is_critical,is_resolved\n']
    choices = ['low', 'medium', 'high']
    for i in range(n_rows):
        lvl = rnd.choice(choices)
        crit = 'true' if lvl == 'high' else 'false'
        resolved = 'true' if rnd.random() < 0.7 else 'false'
        parts.append(f'{i},{lvl},{crit},{resolved}\n'.encode())
    return b''.join(parts)


PATTERNS = [
    ('status_constant', gen_constant),
    ('status_alternating', gen_alternating),
    ('status_bursty', gen_bursty),
    ('is_error_dominant', gen_error_dominant),
    ('bool_random_dist', gen_random_dist),
]
SIZES_KB = [50, 100, 200, 500]
SEEDS = {'status_constant': 20, 'status_alternating': 21, 'status_bursty': 22,
          'is_error_dominant': 23, 'bool_random_dist': 24}
for name, fn in PATTERNS:
    for kb in SIZES_KB:
        p = os.path.join(OUT, f'delta_{name}_{kb}kb.csv')
        data = fn(kb, SEEDS[name])
        with open(p, 'wb') as f:
            f.write(data)
        print(f'  wrote {p} ({len(data)} B)')
print('done')
