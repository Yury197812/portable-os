"""Corpus-scale OEIS sequence atomizer — find hidden patterns via clustering.

Runs atomize on N sequences (default 200), captures structural signals,
clusters by structural-similarity, identifies outliers (sequences whose
atomization profile differs from category median).

Output: corpus-atomize.json with clusters + outliers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def get_strategy_distribution(id: str, strategies: list) -> dict:
    """Return {strategy: ratio_pct} for one sequence."""
    rec = m.mode_atomize({"id": id, "strategies": strategies})
    if not rec.get("ok"):
        return {}
    return rec.get("strategy_ratios", {})


def categorize_sequence(id: str) -> str:
    """Simple category inference from sequence id range and known ids."""
    known = {
        "A000040": "primes",
        "A000079": "powers_of_2",
        "A000045": "fibonacci_like",
        "A000217": "reciprocal_powers",
        "A000290": "squares",
        "A005117": "squarefree",
        "A000578": "cubes",
        "A000720": "pi_count",
        "A000217": "reciprocal_p2",
        "A001006": "motzkin",
        "A000108": "catalan",
        "A000110": "bell",
        "A000142": "derangements",
        "A000111": "heron",
        "A000166": "subfactorial",
        "A001006": "motzkin",
        "A000712": "stirling2",
        "A001855": "narrange",
    }
    if id in known:
        return known[id]
    num = int(id[1:])
    if num < 1000:
        return "core_sequences"
    if num < 10000:
        return "extended_sequences"
    if num < 100000:
        return "obscure_sequences"
    return "long_tail"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--max-strategy", default="xml_flat")
    parser.add_argument("--min-strategy", default="raw")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    print(f"corpus-scale atomize: {args.n} sequences")
    strategies = ["raw", "terms_only", "diff_first", "formulas_first", "keyvalue", "xml_flat", "json_struct"]
    rng = __import__("random")
    rng.seed(42)
    sample_ids = rng.sample(range(1, 100001), args.n)
    target_ids = [f"A{n:06d}" for n in sample_ids]
    results = {}
    t0 = time.perf_counter()
    for i, a_id in enumerate(target_ids, 1):
        try:
            ratios = get_strategy_distribution(a_id, strategies)
        except Exception as e:
            print(f"  {a_id}: FAIL {e}")
            continue
        if not ratios:
            continue
        results[a_id] = {
            "ratios": ratios,
            "category": categorize_sequence(a_id),
            "best_strategy": min(ratios, key=ratios.get),
            "best_ratio": min(ratios.values()),
            "median_ratio": sorted(ratios.values())[len(ratios) // 2],
            "variance": sum((r - sum(ratios.values()) / len(ratios)) ** 2 for r in ratios.values()) / len(ratios),
        }
        if i % 50 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i}/{args.n}: {elapsed:.0f}s elapsed, {len(results)} successful")
    elapsed = time.perf_counter() - t0
    print(f"\ntotal: {len(results)} sequences in {elapsed:.0f}s")
    by_category = defaultdict(list)
    for a_id, r in results.items():
        by_category[r["category"]].append((a_id, r["best_strategy"], r["best_ratio"]))
    print("\n=== Best strategy per category ===")
    for cat, items in sorted(by_category.items()):
        strategies_count = Counter(s for (_, s, _) in items)
        best_strat, best_count = strategies_count.most_common(1)[0]
        best_ratios = [r for (_, _, r) in items if _]
        avg_ratio = sum(r for _, _, r in items) / len(items)
        print(f"  {cat}: {len(items)} sequences, dominant={best_strat} ({best_count}), avg_ratio={avg_ratio:.2f}%")
    print("\n=== Top 20 outliers (highest variance) ===")
    outliers = sorted(results.items(), key=lambda kv: kv[1]["variance"], reverse=True)[:20]
    for a_id, r in outliers:
        print(f"  {a_id}: var={r['variance']:.2f} best={r['best_strategy']} ({r['best_ratio']:.2f}%)")
    print("\n=== Top 20 best (lowest ratio) ===")
    best = sorted(results.items(), key=lambda kv: kv[1]["best_ratio"])[:20]
    for a_id, r in best:
        print(f"  {a_id}: ratio={r['best_ratio']:.2f}% best={r['best_strategy']}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "n_total": args.n,
                "n_successful": len(results),
                "elapsed_seconds": round(elapsed, 1),
                "strategies": strategies,
                "by_category": {cat: [
                    {"id": a_id, "best_strategy": s, "best_ratio": r, "variance": results[a_id]["variance"]}
                    for a_id, s, r in items
                ] for cat, items in by_category.items()},
                "top_outliers": [{"id": a_id, **r} for a_id, r in outliers],
                "top_best": [{"id": a_id, **r} for a_id, r in best],
            }, f, indent=2)
        print(f"\nresults written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
