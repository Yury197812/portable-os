"""Investigate hash 696 cluster (57 sequences).

Why these 57 sequences share hash 696? Find common feature.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-classify\scripts")
import oeis_classify_v7 as v7

data = json.loads(Path(r"D:\4\bha-codecs\benchmark\multi-hash-1024.json").read_text(encoding="utf-8"))
top_buckets = data["top_30_buckets"]
target_sequences = None
for b in top_buckets:
    if b["hash"] == 696:
        target_sequences = b["sequences"]
        break
print(f"hash 696 cluster: {len(target_sequences)} sample sequences")
print(f"sample: {target_sequences}")

first4_dist = Counter()
terms_initial = []
for a_id in target_sequences:
    try:
        first4 = v7.get_first4(a_id)
        if first4:
            first4_dist[first4] += 1
            if len(terms_initial) < 5:
                terms_initial.append((a_id, first4))
    except Exception:
        pass

print(f"\nfirst4 distribution in hash 696:")
for pattern, count in first4_dist.most_common():
    print(f"  {pattern!r}: {count}")

print(f"\nSample sequences:")
for a_id, first4 in terms_initial:
    print(f"  {a_id}: {first4}")
