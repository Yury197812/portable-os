"""Improved cluster using get_first4 + ratio_bucket + n_terms.

Uses random sampling of 5000 sequences, clusters by improved hash.
"""
import sys
import random
import json
import sqlite3
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-classify\scripts")
import oeis_classify_v7 as v7


def improved_hash(first4, n_terms, ratio_bucket):
    sig = f"{first4}|{n_terms//10:x}|{ratio_bucket}"
    h = 0
    for c in sig:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h % 1024


def main():
    random.seed(42)
    target_ids = [f"A{n:06d}" for n in random.sample(range(1, 100001), 5000)]
    in_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json")
    full_data = json.loads(in_path.read_text(encoding="utf-8-sig"))
    indexed = {}
    for entry in full_data["top_30_best"]:
        indexed[entry["a_id"]] = entry
    for entry in full_data["top_30_worst"]:
        indexed[entry["a_id"]] = entry
    for entry in full_data["top_30_variance"]:
        indexed[entry["a_id"]] = entry
    print(f"indexed: {len(indexed)}")
    conn = sqlite3.connect(v7.DB_PATH)
    bucket_seqs = defaultdict(list)
    n_parsed = 0
    for a_id in target_ids:
        first4 = v7.get_first4(a_id)
        if not first4:
            continue
        row = conn.execute("SELECT n_terms FROM sequences WHERE id = ?", (a_id,)).fetchone()
        if not row:
            continue
        n_terms = row[0]
        rec = indexed.get(a_id, {})
        best_ratio = round(rec.get("ratio", 75.0) / 10) * 10
        key = improved_hash(first4, n_terms, best_ratio)
        bucket_seqs[key].append(a_id)
        n_parsed += 1
    conn.close()
    print(f"parsed: {n_parsed}")
    print(f"unique buckets: {len(bucket_seqs)}")
    density = Counter()
    for h, seqs in bucket_seqs.items():
        if len(seqs) >= 10:
            density["10+"] += 1
        elif len(seqs) >= 5:
            density["5-9"] += 1
        elif len(seqs) >= 2:
            density["2-4"] += 1
        else:
            density["1"] += 1
    print(f"density: {dict(density)}")
    sorted_buckets = sorted(bucket_seqs.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\nTop 30 buckets (improved):")
    for h, seqs in sorted_buckets[:30]:
        print(f"  hash {h}: {len(seqs)} sequences")
    out_path = Path(r"D:\4\bha-codecs\benchmark\improved-cluster-1024.json")
    out = {
        "n_sequences": n_parsed,
        "n_unique_buckets": len(bucket_seqs),
        "density": dict(density),
        "top_30_buckets": [{"hash": h, "size": len(v), "sequences": v[:5]} for h, v in sorted_buckets[:30]],
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8-sig")
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
