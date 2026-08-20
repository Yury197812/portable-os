"""Cluster 5000 sequences into 128 buckets via 7-bit hash.

Compute structural hash from first-4-terms + atomization signature.
Identify which buckets are dense (common patterns) vs sparse (unique patterns).

Each bucket = 1/128 of structural feature space (2^7 cells).
Dense bucket = cluster of similar sequences.
Sparse bucket = unique pattern that needs attention.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def structural_hash(first4: str, ratios: dict) -> int:
    """Compute 7-bit hash from first-4-terms + best_ratio + variance_signature."""
    # Take first 4 chars of combined signature
    sig = first4 + f"|{min(ratios.values()):.0f}|{max(ratios.values()):.0f}"
    h = 0
    for c in sig:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h % 128


def main() -> int:
    in_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json")
    data = json.loads(in_path.read_text(encoding="utf-8"))
    best_strategy_dist = data.get("strategy_by_ratio_bucket", {})
    print(f"input: {in_path.name}")
    print(f"ratio distribution: {best_strategy_dist}")

    # Reload 5000 sequences full detail
    full_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomize.json")
    full_data = json.loads(full_path.read_text(encoding="utf-8"))
    full_results = {}
    for item in full_data["by_category"].items() if isinstance(full_data["by_category"], dict) else []:
        for entry in item[1]:
            full_results[entry["id"]] = entry
    print(f"full: {len(full_results)} sequences")

    # Build hash for each sequence
    bucket_map = defaultdict(list)
    bucket_first4 = defaultdict(Counter)
    bucket_ratio = defaultdict(list)
    sku_counts = Counter()
    for a_id, r in full_results.items():
        try:
            _, _, terms_str = m.fetch_term_string(a_id)
            first4 = ",".join(terms_str.split(",")[:4])
        except Exception:
            continue
        best_strat = r["best_strategy"]
        best_ratio = r["best_ratio"]
        variance = r["variance"]
        h = structural_hash(first4, {"best": best_ratio, "var": variance})
        bucket_map[h].append(a_id)
        bucket_first4[h][first4] += 1
        bucket_ratio[h].append(best_ratio)
        sku_counts[(best_strat, bucket_first4[h][first4])] += 1
    print(f"\ntotal sequences hashed: {len(bucket_map)}")
    print(f"total buckets used: {len(bucket_map)} of 128")

    # Density distribution
    bucket_sizes = sorted(bucket_map.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\n=== TOP 30 BUCKETS (dense) ===")
    print(f"{'bucket':>6} {'size':>5} {'first4':>20} {'avg_ratio':>10} {'var':>8}")
    for h, seqs in bucket_sizes[:30]:
        avg = sum(bucket_ratio[h]) / len(bucket_ratio[h])
        var = sum((r - avg) ** 2 for r in bucket_ratio[h]) / len(bucket_ratio[h])
        first4 = bucket_first4[h].most_common(1)[0][0]
        print(f"{h:>6} {len(seqs):>5} {first4:>20} {avg:>10.2f} {var:>8.2f}")

    print(f"\n=== TOP 30 BUCKETS (sparse = unique patterns) ===")
    sparse = [(h, seqs) for h, seqs in bucket_map.items() if len(seqs) == 1]
    print(f"total singletons: {len(sparse)}")
    for h, seqs in sparse[:30]:
        first4 = bucket_first4[h].most_common(1)[0][0]
        avg = bucket_ratio[h][0]
        print(f"  bucket {h}: {seqs[0]} first4={first4} ratio={avg:.2f}%")

    # Save bucket analysis
    out_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomic-cluster.json")
    out_data = {
        "n_buckets": len(bucket_map),
        "n_singletons": len(sparse),
        "n_dense": len([x for x in bucket_map.values() if len(x) > 10]),
        "top_30_buckets": [
            {
                "bucket": h,
                "size": len(seqs),
                "first4": bucket_first4[h].most_common(1)[0][0],
                "avg_ratio": round(sum(bucket_ratio[h]) / len(bucket_ratio[h]), 2),
                "variance": round(sum((r - sum(bucket_ratio[h]) / len(bucket_ratio[h])) ** 2 for r in bucket_ratio[h]) / len(bucket_ratio[h]), 2),
            }
            for h, seqs in bucket_sizes[:30]
        ],
        "all_singletons": [
            {"bucket": h, "id": seqs[0], "first4": bucket_first4[h].most_common(1)[0][0], "ratio": round(bucket_ratio[h][0], 2)}
            for h, seqs in sparse
        ],
    }
    out_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
