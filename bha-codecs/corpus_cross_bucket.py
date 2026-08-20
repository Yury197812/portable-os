"""Find cross-bucket sequences — sequences that fall in multiple buckets.

Cross-bucket = recurring structural signature (atoms appear in multiple
buckets simultaneously because different feature hashes collide on the same
sequence).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def full_hash(first4: str, best_ratio: float, n_terms: int, offset: int) -> int:
    sig = f"{first4}|{best_ratio:.0f}|{n_terms//10:x}|{offset:x}"
    h = 0
    for c in sig:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h


def main() -> int:
    rng = __import__("random")
    rng.seed(42)
    target_ids = [f"A{n:06d}" for n in rng.sample(range(1, 100001), 5000)]
    in_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json")
    full_data = json.loads(in_path.read_text(encoding="utf-8"))
    indexed = {}
    for entry in full_data["top_30_best"]:
        indexed[entry["a_id"]] = entry
    for entry in full_data["top_30_worst"]:
        indexed[entry["a_id"]] = entry
    for entry in full_data["top_30_variance"]:
        indexed[entry["a_id"]] = entry
    print(f"indexed: {len(indexed)} sequences")
    bucket_features = defaultdict(set)
    sequence_buckets = defaultdict(set)
    n_parsed = 0
    for a_id in target_ids:
        try:
            offset, n_terms, terms_str = m.fetch_term_string(a_id)
        except Exception:
            continue
        first4 = ",".join(terms_str.split(",")[:4])
        rec = indexed.get(a_id, {})
        best_ratio = rec.get("ratio", 75.0)
        bucket = full_hash(first4, best_ratio, n_terms, offset) % 1024
        bucket_features[bucket].add(a_id)
        sequence_buckets[a_id].add(bucket)
        n_parsed += 1
    print(f"parsed: {n_parsed}")
    multi_bucket = {a_id: len(bks) for a_id, bks in sequence_buckets.items() if len(bks) > 1}
    print(f"sequences in multiple buckets: {len(multi_bucket)}")
    if multi_bucket:
        sorted_multi = sorted(multi_bucket.items(), key=lambda x: x[1], reverse=True)
        print(f"\nTop 30 cross-bucket sequences:")
        for a_id, count in sorted_multi[:30]:
            print(f"  {a_id}: in {count} buckets")
    cross_bucket_patterns = defaultdict(list)
    for a_id, bks in sequence_buckets.items():
        if len(bks) > 1:
            cross_bucket_patterns[frozenset(bks)].append(a_id)
    print(f"\ncross-bucket cluster patterns: {len(cross_bucket_patterns)}")
    out_path = Path(r"D:\4\bha-codecs\benchmark\cross-bucket-1024.json")
    out = {
        "n_sequences": n_parsed,
        "n_multi_bucket": len(multi_bucket),
        "top_30_multi_bucket": sorted_multi[:30] if multi_bucket else [],
        "patterns": {str(k): v for k, v in list(cross_bucket_patterns.items())[:30]},
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
