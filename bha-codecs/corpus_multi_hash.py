"""Find sequences with weak structural signature - same sequence hits multiple alternative hashes.

For each sequence, compute 5 different hash variants:
- hash_a: first4 + ratio + n_terms + offset
- hash_b: first4 + n_terms + offset
- hash_c: last4 + n_terms
- hash_d: first4 + midpoint
- hash_e: ALL features

Find sequences that appear across multiple hash variants.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Art\.mimicode\skills\oeis-sequence-atomizer\scripts")
import oeis_sequence_atomizer as m


def h1(first4, best_ratio, n_terms, offset):
    return hash(f"{first4}|{best_ratio:.0f}|{n_terms//10:x}|{offset:x}") % 1024


def h2(first4, n_terms, offset):
    return hash(f"{first4}|{n_terms//10:x}|{offset:x}") % 1024


def h3(last4, n_terms):
    return hash(f"{last4}|{n_terms//10:x}") % 1024


def h4(first4, midpoint):
    return hash(f"{first4}|{midpoint}") % 1024


def h5(first4, n_terms, offset, last4):
    return hash(f"{first4}|{last4}|{n_terms//10:x}|{offset:x}") % 1024


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
    sequences_by_hash = defaultdict(set)
    n_parsed = 0
    for a_id in target_ids:
        try:
            offset, n_terms, terms_str = m.fetch_term_string(a_id)
        except Exception:
            continue
        try:
            terms_list = []
            for tok in terms_str.split(","):
                t = tok.strip()
                if not t:
                    continue
                try:
                    terms_list.append(int(t))
                except ValueError:
                    break
            if len(terms_list) < 4:
                continue
            first4 = ",".join(str(t) for t in terms_list[:4])
            last4 = ",".join(str(t) for t in terms_list[-4:])
            midpoint = ",".join(str(t) for t in terms_list[len(terms_list)//2 - 2:len(terms_list)//2 + 2])
        except Exception:
            continue
        rec = indexed.get(a_id, {})
        best_ratio = rec.get("ratio", 75.0)
        for h in [h1(first4, best_ratio, n_terms, offset), h2(first4, n_terms, offset), h3(last4, n_terms), h4(first4, midpoint), h5(first4, n_terms, offset, last4)]:
            sequences_by_hash[h].add(a_id)
        n_parsed += 1
    print(f"parsed: {n_parsed}")
    print(f"unique hashes: {len(sequences_by_hash)}")
    print(f"buckets with 5+ sequences: {sum(1 for s in sequences_by_hash.values() if len(s) >= 5)}")
    print(f"buckets with 10+ sequences: {sum(1 for s in sequences_by_hash.values() if len(s) >= 10)}")
    sorted_buckets = sorted(sequences_by_hash.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\nTop 30 buckets (multiple hash variants):")
    for h, seqs in sorted_buckets[:30]:
        print(f"  hash {h}: {len(seqs)} sequences")
    out_path = Path(r"D:\4\bha-codecs\benchmark\multi-hash-1024.json")
    out = {
        "n_sequences": n_parsed,
        "n_unique_hashes": len(sequences_by_hash),
        "top_30_buckets": [
            {"hash": h, "size": len(v), "sequences": list(v)[:5]}
            for h, v in sorted_buckets[:30]
        ],
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nresults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
