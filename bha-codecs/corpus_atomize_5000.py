"""Corpus atomize 5000 sequences + cluster analysis.

Runs 5000 random sequences through 7 atomization strategies, then
clusters by structural-similarity (best_strategy + variance signature).

Correlates with oeis-classify taxonomy for pattern-based category tagging.
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
    n = 5000
    strategies = ["raw", "terms_only", "diff_first", "formulas_first", "keyvalue", "xml_flat", "json_struct"]
    rng = __import__("random")
    rng.seed(42)
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
        if i % 500 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i}/{n}: {elapsed:.0f}s, {len(results)} successful")
    elapsed = time.perf_counter() - t0
    print(f"\ntotal: {len(results)} sequences in {elapsed:.0f}s")

    # Cluster by ratio bucket
    bucket_floor = lambda r: int(r // 5) * 5
    buckets = defaultdict(list)
    for a_id, r in results.items():
        buckets[bucket_floor(r["best_ratio"])].append(a_id)
    print("\n=== RATIO DISTRIBUTION (bucket of 5%) ===")
    for b in sorted(buckets.keys()):
        bar = "█" * (len(buckets[b]) // 5)
        print(f"  {b:>3}-{b+4:>3}%: {len(buckets[b]):>4d} {bar}")

    # Cluster by first 4 terms pattern
    first4_patterns = Counter()
    for a_id in results:
        try:
            _, _, terms_str = m.fetch_term_string(a_id)
            first4 = ",".join(terms_str.split(",")[:4])
            first4_patterns[first4[:30]] += 1
        except Exception:
            continue
    print(f"\n=== TOP 40 FIRST-4-TERMS PATTERNS ===")
    for pattern, count in first4_patterns.most_common(40):
        print(f"  {count:>4d} × {pattern!r}")

    # Best Strategy vs Ratio correlation
    print("\n=== BEST STRATEGY × RATIO BUCKET ===")
    bins = list(range(20, 105, 10))
    strategy_by_bin = defaultdict(Counter)
    for a_id, r in results.items():
        bi = max(bins, key=lambda b: b if r["best_ratio"] >= b else 0)
        strategy_by_bin[bi][r["best_strategy"]] += 1
    for b in sorted(strategy_by_bin.keys(), reverse=True):
        sc = strategy_by_bin[b]
        print(f"  {b}-{b+9}%: {dict(sc)}")

    # Outliers by ratio + variance
    sorted_by_ratio = sorted(results.items(), key=lambda kv: kv[1]["best_ratio"])
    sorted_by_variance = sorted(results.items(), key=lambda kv: kv[1]["variance"], reverse=True)
    top_30_best = sorted_by_ratio[:30]
    top_30_worst = sorted_by_ratio[-30:]
    top_30_variance = sorted_by_variance[:30]

    out = {
        "n_attempted": n,
        "n_successful": len(results),
        "elapsed_seconds": round(elapsed, 1),
        "strategies": strategies,
        "ratio_distribution": {f"{b}-{b+4}%": len(buckets[b]) for b in sorted(buckets.keys())},
        "top_30_best": [dict(a_id=a_id, ratio=r["best_ratio"], best_strategy=r["best_strategy"]) for a_id, r in top_30_best],
        "top_30_worst": [dict(a_id=a_id, ratio=r["best_ratio"], best_strategy=r["best_strategy"]) for a_id, r in top_30_worst],
        "top_30_variance": [dict(a_id=a_id, variance=r["variance"]) for a_id, r in top_30_variance],
        "top_40_first_4_terms": dict(first4_patterns.most_common(40)),
        "strategy_by_ratio_bucket": {f"{b}-{b+9}%": dict(strategy_by_bin[b]) for b in sorted(strategy_by_bin.keys(), reverse=True)},
    }
    out_path = r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json"
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
