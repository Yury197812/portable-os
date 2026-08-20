"""Cluster 5000 sequences into 512 buckets (2^9) with metadata.

Increase from 2^8 to 2^9 — capture more granular structural fingerprints.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def structural_hash(first4: str, best_ratio: float, n_terms: int, offset: int) -> int:
    sig = f"{first4}|{best_ratio:.0f}|{n_terms//10:x}|{offset:x}"
    h = 0
    for c in sig:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h % 512


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
    print(f"indexed from 5000 file: {len(indexed)} sequences")
    buckets = defaultdict(list)
    bucket_meta = defaultdict(lambda: {
        "first4_patterns": Counter(),
        "best_strategies": Counter(),
        "ratios": [],
        "variances": [],
        "n_terms": [],
        "offsets": [],
    })
    n_parsed = 0
    n_skipped = 0
    t0 = time.perf_counter()
    for a_id in target_ids:
        try:
            offset, n_terms, terms_str = m.fetch_term_string(a_id)
        except Exception:
            n_skipped += 1
            continue
        first4 = ",".join(terms_str.split(",")[:4])
        rec = indexed.get(a_id, {})
        best_ratio = rec.get("ratio", 75.0)
        best_strat = rec.get("best_strategy", "xml_flat")
        variance = 100.0 if a_id in indexed else 50.0
        h = structural_hash(first4, best_ratio, n_terms, offset)
        buckets[h].append(a_id)
        meta = bucket_meta[h]
        meta["first4_patterns"][first4] += 1
        meta["best_strategies"][best_strat] += 1
        meta["ratios"].append(best_ratio)
        meta["variances"].append(variance)
        meta["n_terms"].append(n_terms)
        meta["offsets"].append(offset)
        n_parsed += 1
    elapsed = time.perf_counter() - t0
    print(f"parsed: {n_parsed}, skipped: {n_skipped}, in {elapsed:.0f}s")
    print(f"buckets used: {len(buckets)} of 512")
    density_dist = Counter()
    for h, seqs in buckets.items():
        if len(seqs) >= 50:
            density_dist["50+"] += 1
        elif len(seqs) >= 20:
            density_dist["20-49"] += 1
        elif len(seqs) >= 10:
            density_dist["10-19"] += 1
        elif len(seqs) >= 5:
            density_dist["5-9"] += 1
        elif len(seqs) >= 2:
            density_dist["2-4"] += 1
        else:
            density_dist["1"] += 1
    print(f"\n=== BUCKET DENSITY DISTRIBUTION (512 max) ===")
    for k in ["50+", "20-49", "10-19", "5-9", "2-4", "1"]:
        print(f"  {k}: {density_dist[k]} buckets")
    sorted_buckets = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\n=== TOP 20 BUCKETS (dense) ===")
    print(f"{'bucket':>6} {'size':>5} {'first4':>20} {'avg_ratio':>10} {'var':>8}")
    for h, seqs in sorted_buckets[:20]:
        meta = bucket_meta[h]
        avg = sum(meta["ratios"]) / len(meta["ratios"])
        var = sum(meta["variances"]) / len(meta["variances"])
        first4 = meta["first4_patterns"].most_common(1)[0][0]
        print(f"{h:>6} {len(seqs):>5} {first4:>20} {avg:>10.2f} {var:>8.2f}")
    singletons = [(h, seqs) for h, seqs in buckets.items() if len(seqs) == 1]
    print(f"\n=== TOP 30 BUCKETS (singletons = unique patterns) ===")
    for h, seqs in singletons[:30]:
        meta = bucket_meta[h]
        first4 = meta["first4_patterns"].most_common(1)[0][0]
        avg = meta["ratios"][0]
        print(f"  bucket {h}: {seqs[0]} first4={first4} ratio={avg:.2f}%")
    out_buckets = {}
    for h, seqs in buckets.items():
        meta = bucket_meta[h]
        avg_r = sum(meta["ratios"]) / len(meta["ratios"])
        var = sum(meta["variances"]) / len(meta["variances"])
        avg_n = sum(meta["n_terms"]) / len(meta["n_terms"])
        out_buckets[str(h)] = {
            "size": len(seqs),
            "first4_top": meta["first4_patterns"].most_common(5),
            "best_strategies": dict(meta["best_strategies"]),
            "avg_ratio": round(avg_r, 2),
            "avg_variance": round(var, 2),
            "avg_n_terms": round(avg_n, 1),
            "sequences": seqs[:30],
            "singleton": len(seqs) == 1,
        }
    out_path = Path(r"D:\4\bha-codecs\benchmark\corpus-atomic-cluster-512.json")
    out = {
        "n_total": n_parsed,
        "n_skipped": n_skipped,
        "buckets_used": len(buckets),
        "buckets_total": 512,
        "density_distribution": dict(density_dist),
        "top_20_buckets": [{"bucket": h, **out_buckets[str(h)]} for h, _ in sorted_buckets[:20]],
        "singleton_buckets": [
            {"bucket": h, "id": seqs[0], "first4": bucket_meta[h]["first4_patterns"].most_common(1)[0][0],
             "ratio": round(bucket_meta[h]["ratios"][0], 2), "n_terms": bucket_meta[h]["n_terms"][0]}
            for h, seqs in singletons
        ],
        "all_buckets": out_buckets,
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
