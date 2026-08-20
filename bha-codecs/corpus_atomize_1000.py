"""Corpus-scale atomize v2 — 1000 sequences + cluster analysis.

Runs atomize on 1000 sequences, clusters by structural-similarity, finds
patterns within and between clusters.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def strat_dist(id: str, strategies: list) -> dict:
    rec = m.mode_atomize({"id": id, "strategies": strategies})
    if not rec.get("ok"):
        return {}
    return rec.get("strategy_ratios", {})


def main() -> int:
    n = 1000
    strategies = ["raw", "terms_only", "diff_first", "formulas_first", "keyvalue", "xml_flat", "json_struct"]
    rng = __import__("random")
    rng.seed(7)
    target_ids = [f"A{n:06d}" for n in rng.sample(range(1, 100001), n)]
    results = {}
    t0 = time.perf_counter()
    for i, a_id in enumerate(target_ids, 1):
        try:
            ratios = strat_dist(a_id, strategies)
        except Exception:
            continue
        if not ratios:
            continue
        results[a_id] = {
            "best_strategy": min(ratios, key=ratios.get),
            "best_ratio": min(ratios.values()),
            "median_ratio": sorted(ratios.values())[len(ratios) // 2],
            "variance": sum((r - sum(ratios.values()) / len(ratios)) ** 2 for r in ratios.values()) / len(ratios),
            "ratios": ratios,
        }
        if i % 100 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i}/{n}: {elapsed:.0f}s, {len(results)} successful")
    elapsed = time.perf_counter() - t0
    print(f"\ntotal: {len(results)} sequences in {elapsed:.0f}s")

    # Clustering by name prefix
    prefixes = defaultdict(list)
    for a_id, r in results.items():
        n_id = int(a_id[1:])
        prefix = n_id // 1000  # A00, A01, A02, ..., A99
        prefixes[prefix].append((a_id, r["best_ratio"], r["best_strategy"]))
    by_prefix = {}
    for prefix, items in prefixes.items():
        avg = sum(r for _, r, _ in items) / len(items)
        strat_count = Counter(s for _, _, s in items)
        best_strat = strat_count.most_common(1)[0]
        by_prefix[f"A{prefix:03d}xxx"] = {
            "count": len(items),
            "avg_ratio": round(avg, 2),
            "dominant_strategy": best_strat[0],
            "dominant_count": best_strat[1],
        }

    # Clustering by best_ratio
    sorted_by_ratio = sorted(results.items(), key=lambda kv: kv[1]["best_ratio"])
    top_30_best = sorted_by_ratio[:30]
    top_30_worst = sorted_by_ratio[-30:]
    sorted_by_variance = sorted(results.items(), key=lambda kv: kv[1]["variance"], reverse=True)
    top_30_variance = sorted_by_variance[:30]

    # Co-occurrence of best strategies
    best_strategy_count = Counter(r["best_strategy"] for r in results.values())

    # Sequence type detection (first 8 terms)
    first_byte_patterns = Counter()
    for a_id, r in results.items():
        patterns = m.fetch_term_string(a_id)[2]
        first4 = ",".join(patterns.split(",")[:4])
        first_byte_patterns[first4[:20]] += 1

    out = {
        "n_attempted": n,
        "n_successful": len(results),
        "elapsed_seconds": round(elapsed, 1),
        "strategies": strategies,
        "best_strategy_distribution": dict(best_strategy_count),
        "by_prefix": by_prefix,
        "top_30_best": [(a_id, r["best_ratio"], r["best_strategy"]) for a_id, r in top_30_best],
        "top_30_worst": [(a_id, r["best_ratio"], r["best_strategy"]) for a_id, r in top_30_worst],
        "top_30_variance": [(a_id, r["variance"]) for a_id, r in top_30_variance],
        "top_first_byte_patterns": first_byte_patterns.most_common(20),
    }
    import os
    out_path = r"D:\4\bha-codecs\benchmark\corpus-atomize-1000.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nresults written to {out_path}")

    print("\n=== BEST STRATEGY DISTRIBUTION ===")
    for k, v in best_strategy_count.most_common():
        print(f"  {k}: {v} sequences")

    print("\n=== TOP 30 BEST (lowest ratio) ===")
    for a_id, r in top_30_best:
        print(f"  {a_id}: ratio={r['best_ratio']:.2f}% best={r['best_strategy']}")

    print("\n=== TOP 30 WORST (highest ratio) ===")
    for a_id, r in top_30_worst:
        print(f"  {a_id}: ratio={r['best_ratio']:.2f}% best={r['best_strategy']}")

    print("\n=== TOP 30 HIGHEST VARIANCE ===")
    for a_id, r in top_30_variance:
        print(f"  {a_id}: variance={r['variance']:.2f}")

    print("\n=== TOP 20 FIRST-BYTE PATTERNS ===")
    for k, v in first_byte_patterns.most_common(20):
        print(f"  {v:>4d} × {k!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
