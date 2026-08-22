"""Generate 10MB-1GB synthetic fixtures for bha_parallel size-class
benchmark. Mirrors the patterns in gen_delta_fixtures.py but at
larger scales to validate adaptive threshold tuning.

Patterns (4):
  arith   = arithmetic progression idx,i*step
  mixed   = 5-column mixed int+drift+small+count
  html    = HTML+inline-JSON (browser-like)
  json    = JSON array with embedded objects

Sizes: 10MB, 50MB, 100MB, 500MB, 1GB
Total: 20 fixtures (~3.3 GB total)
"""
import os
import random
import time

OUT = r'D:\\4\\bha-codecs\\benchmark'


def gen_arithmetic(target_bytes: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = target_bytes // 12  # ~12 bytes/row "N,N\n"
    a0 = rnd.randint(0, 1000)
    step = rnd.randint(1, 100)
    parts = [b'idx,val\n']
    for i in range(n_rows):
        parts.append(f'{i},{a0 + i*step}\n'.encode())
    return b''.join(parts)


def gen_mixed(target_bytes: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = target_bytes // 30  # 30 bytes/row
    a0, step, b0, bstep, c0, cstep = 100, 7, 1000.0, 0.5, 1, 3
    parts = [b'idx,a_int,b_drift,c_small,d_count\n']
    for i in range(n_rows):
        a = a0 + i * step
        b = int(b0 + bstep * i)
        c = c0 + (i % 5) * cstep
        d = rnd.randint(0, 100)
        parts.append(f'{i},{a},{b},{c},{d}\n'.encode())
    return b''.join(parts)


def gen_html(target_bytes: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><div class="container">']
    body_so_far = sum(len(p) for p in parts)
    i = 0
    while body_so_far < target_bytes:
        parts.append(
            f'<div class="item" data-id="{i:06d}">'
            f'<span class="user">user_{i:05d}</span>'
            f'<span class="email">user{i}@example.com</span>'
            f'<span class="role">{"admin" if i%3==0 else "editor"}</span>'
            f'<span class="time">2026-08-2{i%9}T12:00:0{i%10}Z</span>'
            f'<span class="status">{"active" if i%2 else "inactive"}</span>'
            f'</div>\n'
        )
        body_so_far += len(parts[-1])
        i += 1
    parts.append('</div></body></html>')
    return ''.join(parts).encode('utf-8')


def gen_json(target_bytes: int, seed: int) -> bytes:
    """Generate JSON array until target_bytes."""
    import json
    rnd = random.Random(seed)
    obj = {'hits': {'hits': [], 'total': 0, 'page': 1, 'version': 'v1'}}
    n = 0
    while len(json.dumps(obj)) < target_bytes:
        i = rnd.randint(0, 10000000)
        obj['hits']['hits'].append({
            'id': f'A{i:07d}',
            'type': ['publication', 'dataset', 'poster'][i % 3],
            'title': f'Research item {i} in field of science ' + 'test ' * rnd.randint(0, 3),
            'authors': [
                {'name': f'Author {i:05d}', 'affiliation': f'University {i % 50}'},
                {'name': f'Coauthor {i:05d}', 'affiliation': f'Institute {i % 30}'},
            ],
            'tags': [f'tag_{i%100}', f'field_{i%40}', f'year_{2020 + (i % 6)}'],
            'doi': f'10.5281/zenodo.{1000000 + i}',
            'files': [{'name': f'file_{i}.pdf', 'size': 100000 + i}],
        })
        n += 1
    obj['hits']['total'] = n
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


PATTERNS = [
    ('arith', gen_arithmetic),
    ('mixed', gen_mixed),
    ('html', gen_html),
    ('json', gen_json),
]
SIZES_BYTES = [10_000_000, 50_000_000, 100_000_000, 500_000_000, 1_000_000_000]
SEEDS = {'arith': 30, 'mixed': 31, 'html': 32, 'json': 33}

total_bytes = 0
total_files = 0
t_start = time.perf_counter()
for name, fn in PATTERNS:
    for sz in SIZES_BYTES:
        label = f'{name}_{sz//1_000_000}mb'
        path = os.path.join(OUT, f'large_{label}.csv' if name != 'json' and name != 'html' else f'large_{label}.{"json" if name == "json" else "html"}')
        if os.path.exists(path):
            print(f'  SKIP {label} (exists)')
            continue
        t0 = time.perf_counter()
        data = fn(sz, SEEDS[name])
        dt = time.perf_counter() - t0
        with open(path, 'wb') as f:
            f.write(data)
        sz_actual = os.path.getsize(path)
        total_bytes += sz_actual
        total_files += 1
        print(f'  {label:30s} {sz_actual/1024/1024:>7.1f}MB  ({dt:.1f}s)')

print()
print(f'Total: {total_files} files, {total_bytes/1024/1024/1024:.2f} GB, '
      f'elapsed {time.perf_counter() - t_start:.0f}s')