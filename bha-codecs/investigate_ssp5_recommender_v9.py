"""Investigation T: SSP5 codec recommender v9 — adds locality (IDF) weighting.

v8 scores via:
    score[c] += cb_weight × (1/(distance + ε))

That's distance-weighted k-NN. The missing piece is **locality**: a codec
that appears in MANY neighbours is generic (brotli everywhere); a codec
that appears in FEW neighbours is domain-specific (BHJA1 only near JSON).

The standard information-retrieval measure for this is **inverse document
frequency** (IDF):
    idf(c) = log(N / df(c) + 1)
where N = total neighbours, df(c) = how many neighbours carry label c.

For each query we compute per-neighbour idf of its label and use it as a
secondary weight on the vote. Codecs that appear in a few nearby training
points (locally rare) get amplified; codecs that appear in almost every
neighbour (locally common) get damped. This is the *log-based* weight the
user asked about.

v9 = v8 + locality score:
    score[c] += cb_weight × (1/(d+ε)) × log(1 + N/df(c))

Output:
  D:\4\bha-codecs\benchmark\ssp5-recommender-v9\
    rules.json, loo-results.json, v9-vs-v1-corpus.json
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_recommender_v8 import build_v8_dataset, loo_by_source
from investigate_ssp5_recommender_v7 import fit_knn_class_balanced
from investigate_ssp5_recommender_v2 import _l1


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v9")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# v9 predictor: same model as v8 (class-balanced), but add locality weight
# ------------------------------------------------------------------------"""
def predict_knn_locality(model, f, top_k: int = 5, k_neigh: int = 30):
    norm = model["norm"]
    q = norm.transform(_feat_dict_local(f))
    dists = [(_l1(q, t), i) for i, t in enumerate(model["feats"])]
    dists.sort()

    # Locality: count label frequency in the k_neigh nearest neighbours.
    near = dists[:k_neigh]
    df = Counter(model["labels"][i] for _, i in near)
    N = len(near)

    eps = 1e-3
    scores = Counter()
    for d, i in dists:
        cb = model["weights"][i]
        label = model["labels"][i]
        # locality = log(1 + N/df(label)) — strong when label is rare here,
        # weak when label is everywhere. df defaults to 1 for labels not in
        # the local window (gives max amplification = log(1+N)).
        df_local = df.get(label, 1)
        locality = math.log(1.0 + N / df_local)
        scores[label] += cb / (d + eps) * locality
    return [c for c, _ in scores.most_common()]


def _feat_dict_local(f: dict) -> dict:
    """Identical to v7's _feat_dict; redefined here to keep the file standalone."""
    from investigate_ssp5_recommender_v2 import _feat_dict
    return _feat_dict(f)


def loo_locality(feats, labels, weights, src_kind):
    src_of: dict[str, list[int]] = {}
    src_kind_of: dict[str, str] = {}
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
        ranked = predict_knn_locality(m, feats[idxs[0]])
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
    print(f"\n[T] v9: k-NN + class-balance + locality (k_neigh=30)")
    print(f"    training: {len(feats)} points, {len(set(labels))} codecs")

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN + inverse-sqrt-frequency class weight + IDF locality",
        "locality_formula": "log(1 + N/df(label))  where N=k_neigh=30, df=neighbour doc-freq",
        "training_set": f"{len(feats)} points = 37 synthetic + 50 real-corpus",
        "unique_codecs": len(set(labels)),
        "label_distribution": dict(Counter(labels)),
    }, indent=2))

    print(f"\n[T] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_locality(feats, labels, weights, src_kind)

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

    # Detailed real-only LOO
    print(f"\n[T] Real-only LOO detail:")
    for r in real_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:38s} bha={r['expected']:8s} "
              f"top1={r['top1']:10s} top3={r['ranked'][:3]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    # Summary
    n_top1 = sum(1 for r in real_rows if r["top1"] == r["expected"])
    n_top3 = sum(1 for r in real_rows if r["expected"] in r["ranked"][:3])
    v9_dist = Counter(r["top1"] for r in real_rows)
    print(f"\n  v9 50-file holdout:")
    print(f"    top-1 matches: {n_top1}/{len(real_rows)} = {100*n_top1/len(real_rows):.1f}%")
    print(f"    top-3 contains: {n_top3}/{len(real_rows)} = {100*n_top3/len(real_rows):.1f}%")
    print(f"    v9 top picks: {v9_dist.most_common(10)}")

    rows50 = [
        {"file": r["source"], "bha_magic": r["expected"], "v9_pred": r["top1"],
         "v9_top3": r["ranked"][:3], "v9_matches_bha": r["in_top1"],
         "v9_bha_in_top3": r["in_top3"]}
        for r in real_rows
    ]
    (OUT / "v9-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(real_rows),
        "v9_top1_match_bha": n_top1,
        "v9_top3_match_bha": n_top3,
        "v9_pick_distribution": dict(v9_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[T] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()