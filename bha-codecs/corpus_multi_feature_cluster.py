"""Extended structural feature analysis.

Compute features per sequence:
- first4_terms, monotonicity, sign_changes, second_diff_stability,
- max_of_first10, sum_of_first10, parity_pattern, prime_factor_density
- compress_ratio, variance, best_strategy

Then cluster into 1024 buckets.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def parse_terms(terms_str: str) -> list[int]:
    out = []
    for tok in terms_str.split(","):
        t = tok.strip()
        if not t:
            continue
        try:
            out.append(int(t))
        except ValueError:
            break
    return out


def extract_features(terms: list[int]) -> dict:
    """Compute structural features for a sequence."""
    if len(terms) < 4:
        return {}
    first10 = terms[:10]
    first4 = ",".join(str(t) for t in first10[:4])
    monotonic = 0
    if all(terms[i] <= terms[i+1] for i in range(min(9, len(terms)-1))):
        monotonic = 1
    elif all(terms[i] >= terms[i+1] for i in range(min(9, len(terms)-1))):
        monotonic = -1
    sign_changes = sum(1 for i in range(min(9, len(terms)-1))
                       if (terms[i+1] - terms[i]) * (terms[i+1] - max(terms[i], terms[i+1])) < 0)
    diffs = [terms[i+1] - terms[i] for i in range(min(9, len(terms)-1))]
    diff2 = sum(1 for i in range(len(diffs)-1) if abs(diffs[i+1] - diffs[i]) <= 1)
    diff3 = diff2 / max(len(diffs) - 1, 1) if len(diffs) > 1 else 0
    max_val = max(first10)
    sum_first = sum(first10)
    parity_pattern = "".join("o" if t % 2 == 0 else "e" for t in first10)
    return {
        "first4": first4,
        "monotonic": monotonic,
        "sign_changes": sign_changes,
        "diff2_stability": diff3,
        "max": max_val,
        "sum": sum_first,
        "parity": parity_pattern,
    }


def structural_hash_v2(features: dict) -> int:
    sig = "|".join(str(v) for v in features.values())
    h = 0
    for c in sig:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h % 1024


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
        "features": [],
        "first4_distribution": Counter(),
        "monotonic_distribution": Counter(),
        "parity_distribution": Counter(),
        "ratios": [],
    })
    n_parsed = 0
    n_skipped = 0
    t0 = time.perf_counter()
    for a_id in target_ids:
        try:
            _, n_terms, terms_str = m.fetch_term_string(a_id)
        except Exception:
            n_skipped += 1
            continue
        terms = parse_terms(terms_str)
        features = extract_features(terms)
        if not features:
            continue
        rec = indexed.get(a_id, {})
        features["best_ratio"] = rec.get("ratio", 75.0)
        h = structural_hash_v2(features)
        buckets[h].append(a_id)
        meta = bucket_meta[h]
        meta["features"].append(features)
        meta["first4_distribution"][features["first4"]] += 1
        meta["monotonic_distribution"][features["monotonic"]] += 1
        meta["parity_distribution"][features["parity"]] += 1
        meta["ratios"].append(features["best_ratio"])
        n_parsed += 1
    elapsed = time.perf_counter() - t0
    print(f"parsed: {n_parsed}, skipped: {n_skipped}, in {elapsed:.0f}s")
    print(f"buckets used: {len(buckets)} of 1024")
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
    print(f"\n=== DENSITY DISTRIBUTION (1024 buckets) ===")
    for k in ["50+", "20-49", "10-19", "5-9", "2-4", "1"]:
        print(f"  {k}: {density_dist[k]} buckets")
    sorted_buckets = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\n=== TOP 30 BUCKETS (dense) ===")
    print(f"{'bucket':>6} {'size':>5} {'f4':>16} {'monotonic':>10} {'ratio':>8}")
    for h, seqs in sorted_buckets[:30]:
        meta = bucket_meta[h]
        top_f4 = meta["first4_distribution"].most_common(1)[0][0]
        avg_ratio = sum(meta["ratios"]) / len(meta["ratios"])
        top_mono = meta["monotonic_distribution"].most_common(1)[0][0]
        print(f"{h:>6} {len(seqs):>5} {top_f4:>16} {top_mono:>10} {avg_ratio:>8.2f}")
    singletons = [(h, seqs) for h, seqs in buckets.items() if len(seqs) == 1]
    print(f"\n=== TOP 50 SINGLETONS (unique structural signatures) ===")
    for h, seqs in singletons[:50]:
        meta = bucket_meta[h]
        top_f4 = meta["first4_distribution"].most_common(1)[0][0]
        avg_ratio = meta["ratios"][0]
        print(f"  {h}: {seqs[0]} f4={top_f4} ratio={avg_ratio:.2f}%")
    out_buckets = {}
    for h, seqs in buckets.items():
        meta = bucket_meta[h]
        out_buckets[str(h)] = {
            "size": len(seqs),
            "first4_top": meta["first4_distribution"].most_common(5),
            "monotonic_top": dict(meta["monotonic_distribution"]),
            "parity_top": dict(meta["parity_distribution"]),
            "avg_ratio": round(sum(meta["ratios"]) / len(meta["ratios"]), 2),
            "sequences": seqs[:30],
            "singleton": len(seqs) == 1,
        }
    out_path = Path(r"D:\4\bha-codecs\benchmark\corpus-multi-feature-1024.json")
    out = {
        "n_total": n_parsed,
        "n_skipped": n_skipped,
        "buckets_used": len(buckets),
        "buckets_total": 1024,
        "density_distribution": dict(density_dist),
        "top_30_buckets": [{"bucket": h, **out_buckets[str(h)]} for h, _ in sorted_buckets[:30]],
        "singleton_buckets": [
            {"bucket": h, "id": seqs[0], "first4": bucket_meta[h]["first4_distribution"].most_common(1)[0][0],
             "ratio": round(bucket_meta[h]["ratios"][0], 2)}
            for h, seqs in singletons
        ],
        "all_buckets": out_buckets,
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
