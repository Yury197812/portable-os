"""Investigation N+: SSP5 codec recommender v3 — augmented training set.

v2 (investigate_ssp5_recommender_v2.py) plateaued at LOO top-1 = 5/13 because
13 labelled points is the statistical floor for k-NN. v2 also collapsed
into "brotli" on the 50-file real corpus (38/50 picks) because brotli is
the most-frequent label (4/13) and distance-weighted voting can't escape
class imbalance on tiny datasets.

v3 uses top-5 alternatives from the 42codec matrix as augmented training
points. For each of the 13 sources, we expand to (source_features,
top_k_codec) pairs with rank-based sample weights (1/(rank+1)) so the
actual winner still dominates but the 2nd-5th codecs contribute signal.
That gives 13 × 5 = 65 weighted points spread across more codec families:
   BHCC1 (×5), BHDT1 (×5), BHMD1 (×5), BHMT1 (×5), BHMX1 (×5), ssp5_adapt,
   ssp5_atom, brotli, raw, lzma2, bz2, BHRT1, BHNL1, BHBK1, BHDS1,
   BHCS1, SSP5, BHLZ1, BHTL1, BHST1, BHJA1, BHDS2, BHSD1, SDLT1, ...

Augmentation logic: each source emits 5 weighted samples, one per rank.
The k-NN predictor aggregates by (weight × 1/(distance+eps)) so the
weight propagates into the voting decision. This is essentially a
soft-SMOTE for tiny structured datasets.

Same evaluation pipeline as v2:
  1. Load 13 ground-truth sources from 42codec matrix + top-5 alternatives.
  2. Re-extract features for each source (same generator functions as v2).
  3. Fit distance-weighted k-NN with per-sample weights.
  4. Leave-one-out CV — per-source accuracy.
  5. Compare v1 / v2 / v3 on the 50-file real corpus using cached
     features from D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json.

Artefacts:
  D:\4\bha-codecs\benchmark\ssp5-recommender-v3\rules.json
  D:\4\bha-codecs\benchmark\ssp5-recommender-v3\loo-results.json
  D:\4\bha-codecs\benchmark\ssp5-recommender-v3\v3-vs-v1-corpus.json
"""
from __future__ import annotations

import json
import math
import statistics
import re
import sys
import shutil
import tempfile
from collections import Counter
from pathlib import Path


sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_recommender_v2 import (
    features_from_path,
    _feat_dict,
    Normalizer,
    _l1,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    BOOL_FEATURES,
    KNOWN_EXT,
    KNOWN_DELIM,
    SOURCE_EXT,
    SOURCE_DOMAIN,
    SOURCES_INT,
    SOURCES_BYTE,
    build_dataset,
    shannon_entropy,
)


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v3")
OUT.mkdir(parents=True, exist_ok=True)

MATRIX_PATH = Path(r"D:\4\bha-codecs\benchmark\ssp5-42codec\42codec-results.json")
CORPUS_RESULTS_PATH = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")


# ---------------------------------------------------------------------------
# Load full top-5 per source from the 42codec matrix
# ---------------------------------------------------------------------------
def load_top5_per_source() -> dict[str, list[str]]:
    """source -> [codec_at_rank1, codec_at_rank2, ..., codec_at_rank5]."""
    data = json.loads(MATRIX_PATH.read_text())
    return {r["source"]: [r[1][0] for r in r["top5"]]
            for r in data["results"]}


# ---------------------------------------------------------------------------
# Augmented dataset: each source contributes 5 weighted points
# ---------------------------------------------------------------------------
def build_augmented_dataset(top5: dict[str, list[str]],
                            base_dataset: list[tuple[dict, str]]
                            ) -> tuple[list[dict], list[str], list[float]]:
    """Returns (normed_feats, labels, weights)."""
    feats: list[dict] = []
    labels: list[str] = []
    weights: list[float] = []
    # base_dataset is ordered by source; build a map source -> features
    by_src = {f["_source"]: f for f, _ in base_dataset}
    for src, ranked in top5.items():
        if src not in by_src:
            continue
        base_feat = dict(by_src[src])
        for rank, codec in enumerate(ranked):
            f = dict(base_feat)
            f["_rank"] = rank
            f["_src"] = src
            feats.append(f)
            labels.append(codec)
            # Winner (rank=0) gets weight 1.0; rank 1 -> 0.5; rank 4 -> 0.2.
            # Linear decay keeps the actual winner dominant but lets the
            # runner-ups contribute signal against the brotli majority.
            weights.append(1.0 / (rank + 1))
    return feats, labels, weights


# ---------------------------------------------------------------------------
# Weighted k-NN
# ---------------------------------------------------------------------------
def fit_knn_weighted(feats: list[dict], labels: list[str], weights: list[float]):
    norm = Normalizer()
    norm.fit([_feat_dict(f) for f in feats])
    normed = [norm.transform(_feat_dict(f)) for f in feats]
    return {"norm": norm, "feats": normed, "labels": labels, "weights": weights}


def predict_knn_weighted(model: dict, f: dict, top_k: int = 5) -> list[str]:
    norm = model["norm"]
    q = norm.transform(_feat_dict(f))
    dists = [(_l1(q, t), i) for i, t in enumerate(model["feats"])]
    dists.sort()
    eps = 1e-3
    scores: Counter = Counter()
    for d, i in dists:
        w = model["weights"][i] / (d + eps)
        scores[model["labels"][i]] += w
    return [c for c, _ in scores.most_common()]


# ---------------------------------------------------------------------------
# LOO with augmentation: when holding out source X, drop ALL 5 of X's
# points, not just one. Otherwise the k-NN sees its siblings.
# ---------------------------------------------------------------------------
def loo(top5: dict[str, list[str]],
        feats: list[dict], labels: list[str], weights: list[float]):
    src_indices: dict[str, list[int]] = {}
    for i, f in enumerate(feats):
        src_indices.setdefault(f["_src"], []).append(i)

    out = []
    for held_src in top5.keys():
        if held_src not in src_indices:
            continue
        held_idx = set(src_indices[held_src])
        train_f = [feats[i] for i in range(len(feats)) if i not in held_idx]
        train_l = [labels[i] for i in range(len(feats)) if i not in held_idx]
        train_w = [weights[i] for i in range(len(feats)) if i not in held_idx]
        model = fit_knn_weighted(train_f, train_l, train_w)
        # Use the first held-out point's features as the query.
        held_feat = feats[src_indices[held_src][0]]
        ranked = predict_knn_weighted(model, held_feat)
        expected = top5[held_src][0]
        out.append({
            "source": held_src,
            "expected_winner": expected,
            "predicted_top1": ranked[0] if ranked else "?",
            "ranked": ranked,
            "in_top1": ranked and ranked[0] == expected,
            "in_top3": expected in ranked[:3],
            "in_top5": expected in ranked[:5],
        })
    return out


# ---------------------------------------------------------------------------
# Compare v3 vs v1 on 50-file real corpus
# ---------------------------------------------------------------------------
REAL_CODECS = {"brotli", "bz2", "zlib", "lzma2", "ssp5", "raw",
               "BHCC1", "BHVT1", "BHSP1", "BHCS1", "BHDS1", "BHDS2",
               "BHDS3", "BHBK1", "BHSC1", "BHJA1", "BHNL1", "BHST1",
               "BHLZ1", "BHTL1", "BHRT1", "BHTM1", "BHMX1", "BHMD1",
               "BHQC1", "BHMX1", "BHDS3", "BHSD1", "SDLT1",
               "ours_adaptive_atomize", "ssp5_atom", "ssp5_adapt",
               "adaptive", "atomize"}


def main():
    print("[N+] loading 42codec matrix + top-5 per source...")
    top5 = load_top5_per_source()
    for src, ranked in top5.items():
        print(f"  {src:18s} top5={ranked}")

    # Reuse v2's base dataset (already extracts features).
    print("\n[N+] building augmented dataset (13 src × 5 ranks = 65 pts)...")
    ground = {src: ranked[0] for src, ranked in top5.items()}
    base_dataset = build_dataset(ground)
    feats, labels, weights = build_augmented_dataset(top5, base_dataset)
    n_unique_labels = len(set(labels))
    print(f"  total samples: {len(feats)}, unique codecs: {n_unique_labels}")
    print(f"  label distribution: {dict(Counter(labels))}")

    print("\n[N+] fitting weighted k-NN...")
    model = fit_knn_weighted(feats, labels, weights)
    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN with rank-weighted training (1/(rank+1)) and distance-weighted vote",
        "training_set": "13 sources × top-5 codecs from 42codec matrix = 65 weighted points",
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "bool_features": BOOL_FEATURES,
        "label_distribution": dict(Counter(labels)),
        "unique_codecs": n_unique_labels,
    }, indent=2))

    print("\n[N+] leave-one-out cross-validation (whole-source holdout)...")
    loo_rows = loo(top5, feats, labels, weights)
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"  LOO top-1: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"  LOO top-3: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"  LOO top-5: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")
    for r in loo_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:18s} winner={r['expected_winner']:12s} "
              f"top1={r['predicted_top1']:12s} ranked={r['ranked']}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    # ----- 50-file real corpus -----
    print("\n[N+] comparing v1 vs v3 on 50-file real corpus...")
    sys.path.insert(0, r"D:\4\bha-codecs")
    from investigate_ssp5_recommender import recommend as v1_recommend

    corpus_data = json.loads(CORPUS_RESULTS_PATH.read_text())
    rows50 = []
    for row in corpus_data["rows"]:
        f = dict(row["features"])
        f["_domain"] = "byte"
        if f.get("ext") == ".csv" and f.get("mean_cols", 0) >= 4:
            f["_domain"] = "int"
        elif f.get("ext") == ".log" and f.get("has_numeric") and f.get("ascii_ratio", 0) > 0.9:
            f["_domain"] = "int"
        v1_pred = row.get("predicted_codec", "?")
        v3_ranked = predict_knn_weighted(model, f, top_k=5)
        v3_pred = v3_ranked[0] if v3_ranked else "?"
        rows50.append({
            "file": row["file"],
            "real_bha_magic": row.get("bha_magic"),
            "real_bha_size": row["bha_size"],
            "real_bha_pct": row["bha_pct"],
            "v1_pred": v1_pred,
            "v3_pred": v3_pred,
            "v3_top5": v3_ranked[:5],
            "v1_real_codec": v1_pred in REAL_CODECS,
            "v3_real_codec": v3_pred in REAL_CODECS,
            "v3_in_bha_top5": row.get("bha_magic") in v3_ranked[:5],
        })

    n_v3_real = sum(1 for r in rows50 if r["v3_real_codec"])
    n_v1_real = sum(1 for r in rows50 if r["v1_real_codec"])
    n_v3_bh = sum(1 for r in rows50 if r["v3_pred"].startswith("BH"))
    n_v1_bh = sum(1 for r in rows50 if r["v1_pred"].startswith("BH"))
    n_v3_in_top5 = sum(1 for r in rows50 if r["v3_in_bha_top5"])
    print(f"\n  v1: real-codec {n_v1_real}/{len(rows50)}, BH-family {n_v1_bh}/{len(rows50)}")
    print(f"  v3: real-codec {n_v3_real}/{len(rows50)}, BH-family {n_v3_bh}/{len(rows50)}")
    print(f"  v3: BHA's actual magic in top-5 = {n_v3_in_top5}/{len(rows50)}")

    v1_dist = Counter(r["v1_pred"] for r in rows50)
    v3_dist = Counter(r["v3_pred"] for r in rows50)
    print(f"\n  v1 top picks: {v1_dist.most_common(8)}")
    print(f"  v3 top picks: {v3_dist.most_common(8)}")

    (OUT / "v3-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(rows50),
        "v1_real_codec_count": n_v1_real,
        "v3_real_codec_count": n_v3_real,
        "v1_bh_family_count": n_v1_bh,
        "v3_bh_family_count": n_v3_bh,
        "v3_bha_magic_in_top5": n_v3_in_top5,
        "v1_pick_distribution": dict(v1_dist),
        "v3_pick_distribution": dict(v3_dist),
        "rows": rows50,
    }, indent=2))

    print("\n[N+] done.")
    print(f"  artefacts in {OUT}/")
    print(f"  - rules.json              (augmented k-NN model)")
    print(f"  - loo-results.json        (top-1={n_top1}/{len(loo_rows)})")
    print(f"  - v3-vs-v1-corpus.json    (50-file comparison)")


if __name__ == "__main__":
    main()