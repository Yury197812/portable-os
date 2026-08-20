"""Investigation S: SSP5 codec recommender v8 — v7 + 50 real-corpus training points.

v7 plateaued at LOO top-5 = 97.3% on the 37-source synthetic set, but on the
50-file real corpus v7's recommended codec matched BHA's actual choice in
0/50 cases (bha_magic in top-5 = 0/50). The reason: v7 was trained ONLY on
37 synthetic sources — it never saw real file fingerprints.

The 50-file corpus JSON (D:\\4\\bha-codecs\\benchmark\\recommender-corpus\\
corpus-results.json) contains:
  - features per file (already-extracted by v1 in a previous run)
  - bha_magic = the actual codec BHA chose for that file (ground truth)
  - bha_size = resulting size

These 50 points are MUCH higher signal than synthetic ones because they
came from BHA's own codec selector.

v8 adds them to v7's training set:
  - 37 synthetic sources (brotli / bz2 / lzma2 / BHA-envelope combos winner)
  - 50 real corpus files (bha_magic winner)
  = 87 training points, ~17 unique codecs

LOO is now done two ways:
  - leave-one-of-37-synthetic-out  -> synthetic-only LOO
  - leave-one-of-50-real-out       -> real-only LOO (new, meaningful)
  - leave-one-of-87-out            -> combined LOO (mixes both)

We measure "real-only LOO" hit rate = how often v8 predicts the actual
bha_magic for a held-out real file. This is the metric v7 was missing.

Output:
  D:\\4\\bha-codecs\\benchmark\\ssp5-recommender-v8\\
    rules.json, loo-results.json (synthetic LOO + real LOO),
    v8-vs-v1-corpus.json (50-file holdout predictions)
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")

# v7 plumbing
from investigate_ssp5_recommender_v7 import (
    build_extended_dataset as build_v7_dataset,
    fit_knn_class_balanced, predict_knn,
    CORPUS_RESULTS_PATH,
)
from investigate_ssp5_recommender_v2 import (
    features_from_path, _feat_dict, Normalizer, _l1,
)


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v8")
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp_sources"
TMP.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Load 50 real-corpus entries (features + bha_magic ground truth)
# ---------------------------------------------------------------------------
def load_real_corpus_points() -> tuple[list[dict], list[str]]:
    """Return (features_per_file, ground_truth_bha_magic_per_file)."""
    corpus_data = json.loads(CORPUS_RESULTS_PATH.read_text())
    feats, labels = [], []
    for row in corpus_data["rows"]:
        f = dict(row["features"])
        f["_source"] = row["file"]
        f["_domain"] = "byte"
        if f.get("ext") == ".csv" and f.get("mean_cols", 0) >= 4:
            f["_domain"] = "int"
        elif f.get("ext") == ".log" and f.get("has_numeric") and f.get("ascii_ratio", 0) > 0.9:
            f["_domain"] = "int"
        # bha_magic may be "SSP5\x03" or "BHNL1" or similar — strip control
        # chars and keep the magic as a label.
        bha_magic = row.get("bha_magic", "").rstrip("\x00")
        if not bha_magic or bha_magic == "raw":
            # raw raw = no codec (uncompressible); use raw as label.
            bha_magic = "raw"
        # Normalize common aliases so bha_magic aligns with v7 codec names.
        if bha_magic.startswith("SSP5"):
            bha_magic = "lzma2"  # base SSP5 envelope = plain LZMA2 + header
        feats.append(f)
        labels.append(bha_magic)
    return feats, labels


# ---------------------------------------------------------------------------
# Build combined training set: v7 synthetic + 50 real-corpus
# ---------------------------------------------------------------------------
def build_v8_dataset() -> tuple[list[dict], list[str], list[float], dict]:
    """Returns (feats, labels, weights, src_kind).

    src_kind[i] in {"synthetic", "real"} tracks provenance for LOO splits.
    """
    print("[S] building v7 training set (37 synthetic sources)...")
    v7_feats, v7_labels, v7_weights = build_v7_dataset()
    print(f"  v7: {len(v7_feats)} points, {len(set(v7_labels))} codecs")

    print("[S] loading 50 real-corpus points...")
    real_feats, real_labels = load_real_corpus_points()
    real_weights = [1.0] * len(real_feats)
    print(f"  real: {len(real_feats)} points, {len(set(real_labels))} codecs")
    print(f"  real label dist: {dict(Counter(real_labels))}")

    feats = v7_feats + real_feats
    labels = v7_labels + real_labels
    weights = v7_weights + real_weights
    src_kind = ["synthetic"] * len(v7_feats) + ["real"] * len(real_feats)

    n_total = len(feats)
    n_unique = len(set(labels))
    print(f"\n[S] combined: {n_total} points, {n_unique} unique codecs")
    print(f"     distribution: {dict(Counter(labels))}")
    return feats, labels, weights, src_kind


# ---------------------------------------------------------------------------
# LOO with kind-aware holdout
# ---------------------------------------------------------------------------
def loo_by_source(feats, labels, weights, src_kind):
    """Group by (_source). Return per-source predictions."""
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
        # Use the first held-out point's features as the query.
        query_feat = feats[idxs[0]]
        ranked = predict_knn(m, query_feat)
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
    print(f"\n[S] fitting class-balanced k-NN on {len(feats)} points...")
    model = fit_knn_class_balanced(feats, labels, weights)

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN with inverse-sqrt-frequency class weights + distance vote",
        "training_set": f"{len(feats)} points = 37 synthetic + 50 real-corpus",
        "unique_codecs": len(set(labels)),
        "label_distribution": dict(Counter(labels)),
    }, indent=2))

    print(f"\n[S] LOO by source ({len(feats)} folds, kind-aware)...")
    loo_rows = loo_by_source(feats, labels, weights, src_kind)

    syn_rows = [r for r in loo_rows if r["kind"] == "synthetic"]
    real_rows = [r for r in loo_rows if r["kind"] == "real"]

    print(f"\n  --- synthetic-only LOO ({len(syn_rows)} sources) ---")
    n_top1_s = sum(1 for r in syn_rows if r["in_top1"])
    n_top3_s = sum(1 for r in syn_rows if r["in_top3"])
    n_top5_s = sum(1 for r in syn_rows if r["in_top5"])
    print(f"    top-1: {n_top1_s}/{len(syn_rows)} = {100*n_top1_s/len(syn_rows):.1f}%")
    print(f"    top-3: {n_top3_s}/{len(syn_rows)} = {100*n_top3_s/len(syn_rows):.1f}%")
    print(f"    top-5: {n_top5_s}/{len(syn_rows)} = {100*n_top5_s/len(syn_rows):.1f}%")

    print(f"\n  --- real-only LOO ({len(real_rows)} files) ---")
    n_top1_r = sum(1 for r in real_rows if r["in_top1"])
    n_top3_r = sum(1 for r in real_rows if r["in_top3"])
    n_top5_r = sum(1 for r in real_rows if r["in_top5"])
    print(f"    top-1: {n_top1_r}/{len(real_rows)} = {100*n_top1_r/len(real_rows):.1f}%")
    print(f"    top-3: {n_top3_r}/{len(real_rows)} = {100*n_top3_r/len(real_rows):.1f}%")
    print(f"    top-5: {n_top5_r}/{len(real_rows)} = {100*n_top5_r/len(real_rows):.1f}%")

    # Combined LOO
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"\n  --- combined LOO ({len(loo_rows)} sources) ---")
    print(f"    top-1: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"    top-3: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"    top-5: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")

    # Detailed real-only LOO (the meaningful one)
    print(f"\n[S] Real-only LOO detail:")
    for r in real_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:38s} bha_magic={r['expected']:8s} "
              f"top1={r['top1']:10s} top3={r['ranked'][:3]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    # Per-source real holdout for diagnostics
    print(f"\n[S] Real-corpus 50-file holdout (each held, others visible)...")
    # Re-fit using all real points so we can predict for held-one.
    # Note: real_only LOO already does this above; we just compare to v7's
    # in-corpus predictions.
    from investigate_ssp5_recommender import recommend as v1_recommend
    rows50 = []
    n_v8_real = 0
    n_v8_top1_real = 0
    n_v8_top3_real = 0
    n_v8_bha = 0
    n_v8_bha_top3 = 0
    for row in real_rows:
        # Pull file features back out of the LOO row for evaluation display.
        f = feats[loo_rows.index(row)]
        v1_pred = v1_recommend(f)[0] if False else None  # not used here
        ranked = row["ranked"]
        v8_pred = row["top1"]
        if v8_pred in (
            "brotli", "bz2", "zlib", "lzma2", "ssp5", "raw",
            "BHCC1", "BHVT1", "BHSP1", "BHCS1", "BHDS1", "BHDS2",
            "BHDS3", "BHBK1", "BHSC1", "BHJA1", "BHNL1", "BHST1",
            "BHLZ1", "BHTL1", "BHRT1", "BHTM1", "BHMX1", "BHMD1",
            "BHQC1", "BHSD1", "SDLT1",
            "ours_adaptive_atomize", "ssp5_atom", "ssp5_adapt",
            "adaptive", "atomize",
        ):
            n_v8_real += 1
        if v8_pred.startswith("BH"):
            n_v8_bha += 1
        if v8_pred == row["expected"]:
            n_v8_top1_real += 1
        if row["in_top3"]:
            n_v8_top3_real += 1
        if row["expected"] in ranked[:3]:
            n_v8_bha_top3 += 1
        rows50.append({
            "file": row["source"],
            "bha_magic": row["expected"],
            "v8_pred": v8_pred,
            "v8_top3": ranked[:3],
            "v8_matches_bha": row["in_top1"],
            "v8_bha_in_top3": row["expected"] in ranked[:3],
        })

    print(f"\n  v8 (50-file holdout):")
    print(f"    top-1 matches bha_magic: {n_v8_top1_real}/{len(real_rows)} = "
          f"{100*n_v8_top1_real/len(real_rows):.1f}%")
    print(f"    top-3 contains bha_magic: {n_v8_top3_real}/{len(real_rows)} = "
          f"{100*n_v8_top3_real/len(real_rows):.1f}%")
    print(f"    v8 picks BH-family codec: {n_v8_bha}/{len(real_rows)}")
    print(f"    v8 bha_magic in top-3: {n_v8_bha_top3}/{len(real_rows)}")

    v8_dist = Counter(r["v8_pred"] for r in rows50)
    print(f"  v8 top picks: {v8_dist.most_common(10)}")

    (OUT / "v8-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(real_rows),
        "v8_top1_match_bha": n_v8_top1_real,
        "v8_top3_match_bha": n_v8_top3_real,
        "v8_picks_bh_family": n_v8_bha,
        "v8_bha_in_top3": n_v8_bha_top3,
        "v8_pick_distribution": dict(v8_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[S] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()