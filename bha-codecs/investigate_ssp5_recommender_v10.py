"""Investigation V: SSP5 codec recommender v10 — content-type + size-aware.

Extends v9b with two new features:
  1. is_json (bool): 1 if file is detected as JSON, 0 otherwise
     - detection: extension in {'.json', '.jsonl'} OR
       first non-whitespace byte is '{' or '['
  2. log_size (numeric): log10(input_bytes) - 2 (centered around 100 bytes)
     - gives k-NN a continuous size signal

Then adds size+type decision rule applied AFTER the k-NN vote,
to leverage the empirical crossover data (commit 28dd6778):
  - JSON files >= 200KB: BHA preprocessor preferred (bha/BH* codecs win)
  - HTML files >= 400KB: brotli wins
  - All other cases: defer to k-NN

Approach: hybrid = v9b's locality-aware k-NN + a small
type/size-specific bias added to the score of selected codecs.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\\bha-codecs")
from investigate_ssp5_recommender_v8 import build_v8_dataset
from investigate_ssp5_recommender_v7 import fit_knn_class_balanced
from investigate_ssp5_recommender_v2 import _l1, _feat_dict


OUT = Path(r"D:\\4\\bha-codecs\\benchmark\\ssp5-recommender-v10")
OUT.mkdir(parents=True, exist_ok=True)


# Import BHA_DOMINANT from v9b
sys.path.insert(0, r"D:\\4\\bha-codecs")
from investigate_ssp5_recommender_v9b import BHA_DOMINANT


# ---------------------------------------------------------------------------
# v10 feature extension
# ---------------------------------------------------------------------------
import re
_JSON_EXTS = {'.json', '.jsonl'}
_JSON_FIRST_CHARS = {'{', '['}


def _is_json_file(file_path_or_ext: str, first_bytes: bytes = None) -> bool:
    """Heuristic: is this file likely JSON?"""
    # Check extension
    ext = ''
    if '.' in file_path_or_ext:
        ext = '.' + file_path_or_ext.rsplit('.', 1)[-1].lower()
    if ext in _JSON_EXTS:
        return True
    # Check first non-whitespace byte
    if first_bytes:
        for b in first_bytes[:32]:
            if b in (ord(' '), ord('\t'), ord('\n'), ord('\r')):
                continue
            return b in (ord('{'), ord('['))
    return False


def _extended_feat_dict(f: dict) -> dict:
    """v9b feat dict + is_json + log_size."""
    base = _feat_dict(f)
    src = f.get('_source', '')
    ext = '.' + src.rsplit('.', 1)[-1].lower() if '.' in src else ''
    # Read first 32 bytes if file_path available
    first_bytes = None
    fp = f.get('path')
    if fp:
        try:
            with open(fp, 'rb') as fh:
                first_bytes = fh.read(32)
        except Exception:
            pass
    base['is_json'] = 1.0 if _is_json_file(src, first_bytes) else 0.0
    sz = float(f.get('input_bytes', 1))
    base['log_size'] = math.log10(max(sz, 1.0)) - 2.0  # 0 at 100B, 1 at 1KB, 3 at 100KB, 4 at 1MB
    return base


# ---------------------------------------------------------------------------
# v10 predictor: v9b base + size/type-aware bias
# ---------------------------------------------------------------------------
def predict_knn_v10(model, f, top_k: int = 5, k_neigh: int = 30):
    norm = model["norm"]
    q = norm.transform(_extended_feat_dict(f))
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
        # v9b locality: BHA-dominant boost
        if label in BHA_DOMINANT:
            locality = math.log(1.0 + N / df_local)
        else:
            locality = 1.0
        scores[label] += cb / (d + eps) * locality

    # v10: apply size+type bias from crossover benchmark
    # (commit 28dd6778 empirical findings)
    is_json = f.get('is_json_proxy', 0.0)
    sz = float(f.get('input_bytes', 0))
    if is_json and sz >= 200_000:
        # JSON >= 200KB: BHA preprocessor wins by 4-9%
        for bha_label in ('lzma2', 'BHCC1', 'BHNL1', 'BHVT1'):
            if bha_label in scores:
                scores[bha_label] *= 1.5
    elif not is_json and sz >= 400_000:
        # HTML >= 400KB: brotli wins
        if 'brotli' in scores:
            scores['brotli'] *= 1.5

    return [c for c, _ in scores.most_common()]


def loo_v10(feats, labels, weights, src_kind):
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
        # pre-compute is_json proxy for this source
        f0 = dict(feats[idxs[0]])
        # peek at file for is_json detection
        try:
            with open(f0.get('path', ''), 'rb') as fh:
                first_bytes = fh.read(32)
        except Exception:
            first_bytes = None
        f0['is_json_proxy'] = 1.0 if _is_json_file(f0.get('_source', ''), first_bytes) else 0.0
        ranked = predict_knn_v10(m, f0)
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
    print(f"\n[V] v10: content-type + size-aware (built on v9b)")
    print(f"    training: {len(feats)} points, {len(set(labels))} unique labels")
    print(f"    BHA-dominant set: {len(BHA_DOMINANT)} codecs")

    (OUT / "rules.json").write_text(json.dumps({
        "method": "v9b (k-NN + locality) + size/type bias from crossover benchmark",
        "size_type_bias": {
            "json_>=200KB": "BHA preprocessor codec x 1.5",
            "non-json_>=400KB": "brotli x 1.5",
            "else": "no bias",
        },
        "crossover_source": "commit 28dd6778 (BHA vs brotli 100KB-1MB)",
        "bha_dominant_set": sorted(BHA_DOMINANT),
        "training_set": f"{len(feats)} points = 37 synthetic + 50 real-corpus",
    }, indent=2))

    print(f"\n[V] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_v10(feats, labels, weights, src_kind)

    syn_rows = [r for r in loo_rows if r["kind"] == "synthetic"]
    real_rows = [r for r in loo_rows if r["kind"] == "real"]

    n_top1_s = sum(1 for r in syn_rows if r["in_top1"])
    n_top3_s = sum(1 for r in syn_rows if r["in_top3"])
    n_top5_s = sum(1 for r in syn_rows if r["in_top5"])
    n_top1_r = sum(1 for r in real_rows if r["in_top1"])
    n_top3_r = sum(1 for r in real_rows if r["in_top3"])
    n_top5_r = sum(1 for r in real_rows if r["in_top5"])
    print(f"  synthetic LOO ({len(syn_rows)}): top-1={n_top1_s}/{len(syn_rows)}, top-3={n_top3_s}, top-5={n_top5_s}")
    print(f"  real      LOO ({len(real_rows)}): top-1={n_top1_r}/{len(real_rows)}, top-3={n_top3_r}, top-5={n_top5_r}")

    print(f"\n[V] Real-only LOO detail:")
    for r in real_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:38s} bha={r['expected']:8s} "
              f"top1={r['top1']:10s} top3={r['ranked'][:3]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    n_top1 = sum(1 for r in real_rows if r["top1"] == r["expected"])
    n_top3 = sum(1 for r in real_rows if r["expected"] in r["ranked"][:3])
    v10_dist = Counter(r["top1"] for r in real_rows)
    print(f"\n  v10 50-file holdout:")
    print(f"    top-1 matches: {n_top1}/{len(real_rows)} = {100*n_top1/len(real_rows):.1f}%")
    print(f"    top-3 contains: {n_top3}/{len(real_rows)} = {100*n_top3/len(real_rows):.1f}%")
    print(f"    v10 top picks: {v10_dist.most_common(10)}")

    (OUT / "v10-vs-v9b.json").write_text(json.dumps({
        "n_files": len(real_rows),
        "v10_top1_match_bha": n_top1,
        "v10_top3_match_bha": n_top3,
        "v10_pick_distribution": dict(v10_dist),
    }, indent=2))

    print(f"\n[V] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()
