"""Generate log/telemetry and IP fixtures for delta preprocessor
benchmark. Two patterns:
  - log_per_sec:  timestamp (epoch seconds, 1 row per sec) + value
  - log_bursty:   timestamp (with 1-100 row bursts, same second) + value
  - ip_sequential: 192.168.1.X where X increments
  - ip_random_in_subnet: 10.X.Y.Z where X varies, Y/Z random in range
  - mixed_log:    timestamp + 2 int metrics + IP (5 columns)
"""
import os
import random
import time

OUT = r'D:\\4\\bha-codecs\\benchmark'

def gen_log_per_sec(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 24
    epoch_start = 1700000000
    parts = [b'ts,level,latency_ms\n']
    for i in range(n_rows):
        ts = epoch_start + i
        level = rnd.randint(0, 100)
        lat = rnd.randint(1, 500)
        parts.append(f'{ts},{level},{lat}\n'.encode())
    return b''.join(parts)


def gen_log_bursty(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 24
    epoch_start = 1700000000
    parts = [b'ts,count\n']
    cur_ts = epoch_start
    for i in range(n_rows):
        cur_ts += rnd.choice([0, 0, 0, 0, 1, 1, 2, 5, 10, 60, 3600])
        cnt = rnd.randint(0, 1000)
        parts.append(f'{cur_ts},{cnt}\n'.encode())
    return b''.join(parts)


def gen_ip_sequential(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 14
    parts = [b'src_ip,dst_ip\n']
    for i in range(n_rows):
        src = f'10.0.0.{(i // 256) % 256}'
        dst = f'192.168.{(i // 65536) % 256}.{i % 256}'
        parts.append(f'{src},{dst}\n'.encode())
    return b''.join(parts)


def gen_ip_random_subnet(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 14
    parts = [b'client_ip\n']
    for _ in range(n_rows):
        ip = f'{rnd.randint(1, 223)}.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}'
        parts.append(f'{ip}\n'.encode())
    return b''.join(parts)


def gen_mixed_log(target_kb: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    n_rows = (target_kb * 1024) // 40
    epoch_start = 1700000000
    parts = [b'ts,user_id,latency_ms,client_ip,status\n']
    for i in range(n_rows):
        ts = epoch_start + i
        uid = rnd.randint(1, 100000)
        lat = rnd.randint(1, 500)
        ip = f'{rnd.randint(1,223)}.{rnd.randint(0,255)}.{rnd.randint(0,255)}.{rnd.randint(1,254)}'
        status = rnd.choice([200, 200, 200, 404, 500])
        parts.append(f'{ts},{uid},{lat},{ip},{status}\n'.encode())
    return b''.join(parts)


PATTERNS = [
    ('log_per_sec', gen_log_per_sec),
    ('log_bursty', gen_log_bursty),
    ('ip_sequential', gen_ip_sequential),
    ('ip_random_subnet', gen_ip_random_subnet),
    ('mixed_log', gen_mixed_log),
]
SIZES_KB = [50, 100, 200, 500]
SEEDS = {'log_per_sec': 10, 'log_bursty': 11, 'ip_sequential': 12,
          'ip_random_subnet': 13, 'mixed_log': 14}
for name, fn in PATTERNS:
    for kb in SIZES_KB:
        p = os.path.join(OUT, f'delta_{name}_{kb}kb.csv')
        data = fn(kb, SEEDS[name])
        with open(p, 'wb') as f:
            f.write(data)
        print(f'  wrote {p} ({len(data)} B)')
print('done')
