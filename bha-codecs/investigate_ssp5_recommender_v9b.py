"""Investigation U: SSP5 codec recommender v9b — locality restricted to BHA-dominant codecs.

v9 failed because locality was computed over ALL label frequencies in the
k-NN ball, which amplified rarely-winning global classes (bz2 at 6/87).
v9b restricts locality to a curated set of BHA-dominant codecs — the ones
BHA actually uses in the 50-file corpus:

  bha_dominant = {lzma2, BHTC1, BHVT1, BHRT1, BHJA1, BHNL1, BHCC1,
                  BHTM1, BHTL1, BHMX1, BHQC1, BHSP1, BHST1, BHDT1,
                  BHCS1, BHBK1, BHDS1, BHDS2, BHRT1, BHRT1NUL, ...}

These are the codecs that appear in the 50-file corpus's bha_magic column.
We compute locality ONLY for these labels; non-dominant labels (brotli, bz2,
zlib, raw, atomize, ...) get locality = 1.0 (no boost, no demote).

v9b score:
    score[c] += cb_weight × (1/(d+ε)) × locality(c)
where
    locality(c) = log(1 + N/df(c))   if c ∈ bha_dominant
                 = 1.0                  otherwise
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_recommender_v8 import build_v8_dataset
from investigate_ssp5_recommender_v7 import fit_knn_class_balanced
from investigate_ssp5_recommender_v2 import _l1


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v9b")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# BHA-dominant codecs: list every BHA_FILE_MAGIC + a few real-codec aliases.
# ---------------------------------------------------------------------------
BHA_DOMINANT = {
    "lzma2",          # alias for SSP5 envelope (alias from v8 normalization)
    # All BHA file_codec magics from investigate_ssp5_42codec.py:159-187
    "BHST1", "BHRT1", "BHVT1", "BHSC1", "BHTC1", "BHTM1", "BHNL1",
    "BHJA1", "BHQC1", "BHCS1", "BHMT1", "BHSP1", "BHDT1", "BHMX1",
    "BHMD1", "BHCC1", "BHTL1", "BHLZ1", "BHDS3", "BHSD1", "SDLT1",
    "BHBK1", "BHDS1", "BHDS2",
    # NUL variants
    "BHSC1NUL", "BHRT1NUL", "BHVT1NUL",
    # Preprocessor combos that won in v6/v7
    "BHCC1__delta_i64", "BHCC1__transpose", "BHCC1__json_extract",
    "BHCC1__collate_keys", "BHCC1__dedup_lines",
    "BHCS1__delta_i64", "BHVT1__delta_i64", "BHRT1__dedup_lines",
    # Raw (small files, no compression)
    "raw",
}


# ---------------------------------------------------------------------------
# v9b predictor: locality only for BHA-dominant classes
# ---------------------------------------------------------------------------
def predict_knn_v9b(model, f, top_k: int = 5, k_neigh: int = 30):
    norm = model["norm"]
    q = norm.transform(_feat_dict_local(f))
    dists = [(_l1(q, t), i) for i, t in enumerate(model["feats"])]
    dists.sort()

    near = dists[:k_neigh]
    df = Counter(model["labels"][i] for _, i in near)
    N = len(near)

    eps = 1e-3
    scores = Counter()
    for d, i in dists:
        cb = model["weights"][i]
        label = model["labels"][i]
        df_local = df.get(label, 1)
        if label in BHA_DOMINANT:
            locality = math.log(1.0 + N / df_local)
        else:
            locality = 1.0  # no boost/demote for non-dominant labels
        scores[label] += cb / (d + eps) * locality
    return [c for c, _ in scores.most_common()]


def _feat_dict_local(f):
    from investigate_ssp5_recommender_v2 import _feat_dict
    return _feat_dict(f)


def loo_v9b(feats, labels, weights, src_kind):
    src_of = {}
    src_kind_of = {}
    for i, f in enumerate(feats):
        src_of.setdefault(f["_source"], []).append(i)
        src_kind_of[f["_source"]] = src_kind[i]
    out = []
    for src, idxs in src_of.items():
        held = set(idxs)
        train_f = [feats[i] for i in range(len(feats)) if i not in held]
        train_l = [labels[i] for i in range(len(feats)) if i not in held]
        train_w = [weights[i] for i in range(len(feats)) if i not in held]
        if not train_f:
            continue
        m = fit_knn_class_balanced(train_f, train_l, train_w)
        ranked = predict_knn_v9b(m, feats[idxs[0]])
        out.append({
            "source": src,
            "kind": src_kind_of[src],
            "expected": labels[idxs[0]],
            "ranked": ranked,
            "top1": ranked[0] if ranked else "?",
            "in_top1": ranked and ranked[0] == labels[idxs[0]],
            "in_top3": labels[idxs[0]] in ranked[:3],
            "in_top5": labels[idxs[0]] in ranked[:5],
        })
    return out


def main():
    feats, labels, weights, src_kind = build_v8_dataset()
    print(f"\n[U] v9b: locality restricted to {len(BHA_DOMINANT)} BHA-dominant codecs")
    print(f"    training: {len(feats)} points, {len(set(labels))} unique labels")

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN + inverse-sqrt class weight + distance + locality(BHA-dominant only)",
        "locality_formula": "log(1 + N/df) if label in bha_dominant else 1.0",
        "bha_dominant_set": sorted(BHA_DOMINANT),
        "training_set": f"{len(feats)} points = 37 synthetic + 50 real-corpus",
        "unique_codecs": len(set(labels)),
    }, indent=2))

    print(f"\n[U] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_v9b(feats, labels, weights, src_kind)

    syn_rows = [r for r in loo_rows if r["kind"] == "synthetic"]
    real_rows = [r for r in loo_rows if r["kind"] == "real"]

    n_top1_s = sum(1 for r in syn_rows if r["in_top1"])
    n_top3_s = sum(1 for r in syn_rows if r["in_top3"])
    n_top5_s = sum(1 for r in syn_rows if r["in_top5"])
    n_top1_r = sum(1 for r in real_rows if r["in_top1"])
    n_top3_r = sum(1 for r in real_rows if r["in_top3"])
    n_top5_r = sum(1 for r in real_rows if r["in_top5"])
    print(f"  synthetic LOO ({len(syn_rows)}): top-1={n_top1_s}, top-3={n_top3_s}, top-5={n_top5_s}")
    print(f"  real      LOO ({len(real_rows)}): top-1={n_top1_r}, top-3={n_top3_r}, top-5={n_top5_r}")

    print(f"\n[U] Real-only LOO detail:")
    for r in real_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:38s} bha={r['expected']:8s} "
              f"top1={r['top1']:10s} top3={r['ranked'][:3]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    n_top1 = sum(1 for r in real_rows if r["top1"] == r["expected"])
    n_top3 = sum(1 for r in real_rows if r["expected"] in r["ranked"][:3])
    v9b_dist = Counter(r["top1"] for r in real_rows)
    print(f"\n  v9b 50-file holdout:")
    print(f"    top-1 matches: {n_top1}/{len(real_rows)} = {100*n_top1/len(real_rows):.1f}%")
    print(f"    top-3 contains: {n_top3}/{len(real_rows)} = {100*n_top3/len(real_rows):.1f}%")
    print(f"    v9b top picks: {v9b_dist.most_common(10)}")

    rows50 = [
        {"file": r["source"], "bha_magic": r["expected"], "v9b_pred": r["top1"],
         "v9b_top3": r["ranked"][:3], "v9b_matches_bha": r["in_top1"],
         "v9b_bha_in_top3": r["in_top3"]}
        for r in real_rows
    ]
    (OUT / "v9b-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(real_rows),
        "v9b_top1_match_bha": n_top1,
        "v9b_top3_match_bha": n_top3,
        "v9b_pick_distribution": dict(v9b_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[U] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()