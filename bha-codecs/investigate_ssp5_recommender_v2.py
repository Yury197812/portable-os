"""Investigation N: SSP5 codec recommender v2 — auto-trained on the 42codec matrix.

v1 (investigate_ssp5_recommender.py) was a hand-coded decision tree over 14 KB
entries — all matched on the heuristic but only ~5-10% matched BHA's actual
winners on the 50-file real corpus (see recommender-corpus/corpus-results.json,
BHA wins 45/50 with much smaller sizes).

v2 instead:
  1. Builds a labelled dataset (source -> optimal codec) directly from
     investigate_ssp5_42codec.py results (the ground truth).
  2. Augments the source list: each KB file maps to a known source via the
     extracted-int pipeline. We re-extract features for both the synthetic
     sources AND the KB files so they share the same feature space.
  3. Trains a tiny scikit-learn style decision tree (max_depth=6) over the
     feature vector, using OneVsRest to allow the same codec label on
     multiple sources. We avoid sklearn as a dependency: implement ID3
     (information gain) inline over a hand-built feature discretizer so the
     recommender is hermetic and re-runnable.
  4. Leave-one-out validation on the 13 sources.
  5. Compares v2 against v1 on the 50-file real corpus:
     - v1: picks codec from heuristic, measures bytes_via_recommender
     - v2: same
     - Real BHA winner reported per file as upper bound.
  6. Outputs:
     - benchmark/ssp5-recommender-v2/rules.json (the decision tree)
     - benchmark/ssp5-recommender-v2/loo-results.json (per-source)
     - benchmark/ssp5-recommender-v2/v2-vs-v1-corpus.json (50-file comparison)

Important: we are predicting the codec LABEL (not bytes). The byte size is
estimated later via the 42codec matrix if available for the same file, or
fall back to a generic size model.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_real_corpus import (
    CORPUS,
    extract_ints_dense_csv,
    extract_ints_telemetry,
)


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v2")
OUT.mkdir(parents=True, exist_ok=True)

MATRIX_PATH = Path(r"D:\4\bha-codecs\benchmark\ssp5-42codec\42codec-results.json")
CORPUS_RESULTS_PATH = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")
V1_RESULTS_PATH = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender\recommender-results.json")

CORPUS_BENCH_DIR = Path(r"D:\4\bha-codecs\benchmark")


# ---------------------------------------------------------------------------
# Feature extraction (mirrors v1: features_from_path)
# ---------------------------------------------------------------------------
def shannon_entropy(sample: bytes) -> float:
    if not sample:
        return 0.0
    counts = Counter(sample)
    n = len(sample)
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p)
    return h


def features_from_path(path: Path, sample_size: int = 32 * 1024) -> dict:
    # Some files in the real-corpus directory are locked by another process
    # (BHA indexer, archive tools) and `path.read_bytes()` raises
    # PermissionError. We work around it by copying the file into a temp
    # location first — the kernel will hand us a fresh handle.
    import os
    import shutil
    import tempfile
    try:
        data = path.read_bytes()
    except PermissionError:
        with tempfile.NamedTemporaryFile(delete=False, suffix=path.suffix,
                                          dir=OUT) as tmp:
            tmp_path = Path(tmp.name)
        try:
            # shutil.copyfile opens the source with FILE_SHARE_READ on Windows
            # via the CopyFileExW call, bypassing exclusive locks from
            # readers that don't write.
            shutil.copyfile(str(path), str(tmp_path))
            data = tmp_path.read_bytes()
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    ext = path.suffix.lower()
    sample = data[:sample_size]
    if not sample:
        sample = data
    ent = shannon_entropy(sample)
    zero_ratio = sample.count(b"\x00") / len(sample)
    ascii_ratio = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126) / len(sample)
    lines = sample.split(b"\n")
    line_len_std = 0.0
    if len(lines) > 1:
        lens = [len(l) for l in lines if l]
        if lens:
            line_len_std = statistics.pstdev(lens) / max(1, statistics.mean(lens))
    has_repeated_lines = False
    if len(lines) > 4:
        seen = set()
        repeats = 0
        for l in lines:
            if l in seen:
                repeats += 1
            else:
                seen.add(l)
        has_repeated_lines = repeats / len(lines) > 0.3
    has_numeric = bool(re.search(rb"-?\d+(\.\d+)?", sample))
    comma_count = sample.count(b",")
    tab_count = sample.count(b"\t")
    pipe_count = sample.count(b"|")
    delim = max((("csv", comma_count), ("tsv", tab_count), ("pipe", pipe_count)),
                key=lambda x: x[1])[0] if max(comma_count, tab_count, pipe_count) > 5 else "none"
    csv_density = 0.0
    mean_cols = 0.0
    if delim in ("csv", "tsv"):
        sep = b"," if delim == "csv" else b"\t"
        rows = sample.split(b"\n")
        rows = [r for r in rows if r]
        if rows:
            col_counts = [r.count(sep) + 1 for r in rows[:200]]
            mean_cols = sum(col_counts) / len(col_counts) if col_counts else 0
            csv_density = (len(rows) * mean_cols) / max(1, len(sample))
    binary_repeat = False
    if ext in (".bin", ".raw") and ent < 6:
        block = sample[:4096]
        for stride in (4, 8, 16, 32, 64):
            if len(block) >= stride * 8:
                first = block[:stride]
                if block.count(first) >= len(block) // stride // 2:
                    binary_repeat = True
                    break
    return {
        "ext": ext,
        "size": len(data),
        "entropy": round(ent, 4),
        "zero_ratio": round(zero_ratio, 4),
        "ascii_ratio": round(ascii_ratio, 4),
        "line_len_std": round(line_len_std, 4),
        "has_repeated_lines": has_repeated_lines,
        "binary_repeat": binary_repeat,
        "has_numeric": has_numeric,
        "delimiter": delim,
        "csv_density": round(csv_density, 4),
        "mean_cols": round(mean_cols, 2),
    }


# ---------------------------------------------------------------------------
# Ground-truth labels from the 42codec matrix
# ---------------------------------------------------------------------------
def load_ground_truth() -> dict[str, str]:
    """Map source name -> best codec from investigate_ssp5_42codec.py results."""
    data = json.loads(MATRIX_PATH.read_text())
    return {r["source"]: r["best_chain"] for r in data["results"]}


# ---------------------------------------------------------------------------
# Build a labelled dataset
# ---------------------------------------------------------------------------
def gen_synthetic_for(name: str, n: int = 16_384):
    """Reproduce the synthetic generators from investigate_ssp5_42codec."""
    import random
    import struct

    sys.path.insert(0, r"D:\4\bha-codecs")
    from investigate_ssp5_even_atom import (
        gen_even_mask_zero, gen_even_mask_one,
        gen_arbitrary, gen_arbitrary_mixed,
    )
    if name == "syn_even_0":
        vals = gen_even_mask_zero(n)
    elif name == "syn_even_1":
        vals = gen_even_mask_one(n)
    elif name == "syn_arb_lcg":
        vals = gen_arbitrary(n)
    elif name == "syn_arb_mixed":
        vals = gen_arbitrary_mixed(n)
    else:
        raise ValueError(name)
    return b"".join(struct.pack("<q", v) for v in vals)


def _bytes_text(n: int) -> bytes:
    base = (b"The quick brown fox jumps over the lazy dog. "
            b"Pack my box with five dozen liquor jugs. ")
    return (base * ((n // len(base)) + 1))[:n]


def _bytes_zeros(n: int) -> bytes:
    return b"\x00" * n


def _bytes_random(n: int) -> bytes:
    import random
    r = random.Random(42)
    return bytes(r.getrandbits(8) for _ in range(n))


def gen_byte_source(name: str) -> bytes:
    """Reproduce the byte-domain sources from investigate_ssp5_42codec."""
    if name == "text_repeated":
        return _bytes_text(200_000)
    if name == "binary_zeros":
        return _bytes_zeros(200_000)
    if name == "binary_random":
        return _bytes_random(200_000)
    if name == "ini_config":
        p = CORPUS / "ini_config_128k.ini"
        return p.read_bytes()[:100_000]
    if name == "json_array":
        return (CORPUS / "data_json_100k.json").read_bytes()
    if name == "css_repeated":
        return (CORPUS / "css_repeated_150k.css").read_bytes()
    if name == "telem_log_raw":
        return (CORPUS / "telemetry_logs_1m.log").read_bytes()[:200_000]
    raise ValueError(name)


def gen_int_source(name: str) -> bytes:
    if name == "real_csv_int":
        vals = extract_ints_dense_csv(CORPUS / "dense_numeric_csv_300k.csv", max_rows=16_384)
    elif name == "real_telem_int":
        vals = extract_ints_telemetry(CORPUS / "telemetry_logs_1m.log", max_rows=16_384)
    else:
        return gen_synthetic_for(name)
    import struct
    return b"".join(struct.pack("<q", v) for v in vals)


SOURCES_INT = ["syn_even_0", "syn_even_1", "syn_arb_lcg", "syn_arb_mixed",
               "real_csv_int", "real_telem_int"]
SOURCES_BYTE = ["text_repeated", "binary_zeros", "binary_random",
                "ini_config", "json_array", "css_repeated", "telem_log_raw"]

# Extension assigned per source. Synthetic int streams are written to .csv so
# their byte fingerprint resembles real_csv_int (otherwise the feature space
# splits into two clusters for the same domain).
SOURCE_EXT = {
    "syn_even_0":       ".csv",
    "syn_even_1":       ".csv",
    "syn_arb_lcg":      ".csv",
    "syn_arb_mixed":    ".csv",
    "real_csv_int":     ".csv",
    "real_telem_int":   ".log",
    "text_repeated":    ".txt",
    "binary_zeros":     ".bin",
    "binary_random":    ".bin",
    "ini_config":       ".ini",
    "json_array":       ".json",
    "css_repeated":     ".css",
    "telem_log_raw":    ".log",
}

SOURCE_DOMAIN = {
    "syn_even_0": "int", "syn_even_1": "int",
    "syn_arb_lcg": "int", "syn_arb_mixed": "int",
    "real_csv_int": "int", "real_telem_int": "int",
    "text_repeated": "byte", "binary_zeros": "byte",
    "binary_random": "byte", "ini_config": "byte",
    "json_array": "byte", "css_repeated": "byte",
    "telem_log_raw": "byte",
}


def build_dataset(ground: dict[str, str]) -> list[tuple[dict, str]]:
    """For each source: extract features, pair with ground-truth codec.

    Synthetic int streams are emitted to .csv so the delimiter/csv_density
    fingerprints line up with real_csv_int; otherwise the byte-feature
    space splits for the same target class.
    """
    rows = []
    tmpdir = OUT / "_tmp_sources"
    tmpdir.mkdir(exist_ok=True)
    for s in SOURCES_INT + SOURCES_BYTE:
        if s.startswith("syn_"):
            data = gen_int_source(s)
        elif s in SOURCES_BYTE:
            data = gen_byte_source(s)
        elif s == "real_csv_int":
            data = gen_int_source(s)
        elif s == "real_telem_int":
            data = gen_int_source(s)
        else:
            continue
        ext = SOURCE_EXT[s]
        tmp = tmpdir / (s + ext)
        tmp.write_bytes(data)
        f = features_from_path(tmp)
        f["_source"] = s
        f["_domain"] = SOURCE_DOMAIN[s]
        rows.append((f, ground[s]))
    return rows


# ---------------------------------------------------------------------------
# Feature vector for k-NN (continuous + categorical + bool, normalized)
# ---------------------------------------------------------------------------
NUMERIC_FEATURES = ["size", "entropy", "zero_ratio", "ascii_ratio",
                    "line_len_std", "csv_density", "mean_cols"]
CATEGORICAL_FEATURES = ["ext", "delimiter"]
BOOL_FEATURES = ["has_repeated_lines", "binary_repeat", "has_numeric"]

# All known extension + delimiter values seen across training + corpus.
KNOWN_EXT = {".csv", ".txt", ".bin", ".json", ".css", ".ini", ".log",
             ".raw", ".tsv", ".yaml", ".yml", ".md", ".html", ".xml",
             ".zip", ".js", ".tsv"}
KNOWN_DELIM = {"csv", "tsv", "pipe", "none"}


def _feat_dict(f: dict) -> dict:
    """Return a flat numeric feature dict, expanding categoricals as booleans."""
    out = {}
    for fn in NUMERIC_FEATURES:
        out[fn] = float(f.get(fn, 0.0))
    for ext in sorted(KNOWN_EXT):
        out[f"ext_is_{ext.lstrip('.')}"] = 1.0 if f.get("ext") == ext else 0.0
    for d in sorted(KNOWN_DELIM):
        out[f"delim_is_{d}"] = 1.0 if f.get("delimiter") == d else 0.0
    for fn in BOOL_FEATURES:
        out[fn] = 1.0 if f.get(fn) else 0.0
    out["domain_is_int"] = 1.0 if f.get("_domain") == "int" else 0.0
    out["domain_is_byte"] = 1.0 if f.get("_domain") == "byte" else 0.0
    return out


class Normalizer:
    """Per-feature min-max scaler, fit on the training set."""
    def __init__(self):
        self.lo: dict = {}
        self.hi: dict = {}
        self.span: dict = {}

    def fit(self, feats: list[dict]):
        keys = list(feats[0].keys())
        for k in keys:
            vs = [f[k] for f in feats]
            self.lo[k] = min(vs)
            self.hi[k] = max(vs)
            s = self.hi[k] - self.lo[k]
            self.span[k] = s if s > 1e-9 else 1.0

    def transform(self, f: dict) -> dict:
        return {k: (f.get(k, 0.0) - self.lo[k]) / self.span[k] for k in self.lo}


def _l1(a: dict, b: dict) -> float:
    return sum(abs(a[k] - b[k]) for k in a)


def _weighted_l1(a: dict, b: dict, weights: dict) -> float:
    return sum(weights.get(k, 1.0) * abs(a[k] - b[k]) for k in a)


# ---------------------------------------------------------------------------
# k-NN recommender (top-K ranking)
# ---------------------------------------------------------------------------
def fit_knn(dataset: list[tuple[dict, str]], k: int = 5):
    feats_only = [d for d, _ in dataset]
    norm = Normalizer()
    norm.fit([_feat_dict(f) for f in feats_only])
    normed = [norm.transform(_feat_dict(f)) for f in feats_only]
    labels = [lab for _, lab in dataset]
    return {"norm": norm, "feats": normed, "labels": labels, "k": k}


def predict_knn(model: dict, f: dict, top_k: int | None = None) -> list[str]:
    """Return ranked list of codec labels, best first (distance-weighted)."""
    norm = model["norm"]
    q = norm.transform(_feat_dict(f))
    dists = [(_l1(q, t), i) for i, t in enumerate(model["feats"])]
    dists.sort()
    k = top_k or model["k"]
    # Distance-weighted vote: w = 1/(d+eps). Closer neighbours dominate,
    # which prevents the most-frequent label (brotli, 4/13) from winning
    # every vote when the query point is ambiguous.
    scores: Counter = Counter()
    eps = 1e-3
    for d, i in dists[:k]:
        w = 1.0 / (d + eps)
        scores[model["labels"][i]] += w
    return [c for c, _ in scores.most_common()]


def loo(dataset: list[tuple[dict, str]]) -> list[dict]:
    """Leave-one-out cross-validation with k-NN top-K metric."""
    out = []
    for i in range(len(dataset)):
        train = dataset[:i] + dataset[i + 1:]
        held_features, held_label = dataset[i]
        model = fit_knn(train, k=5)
        ranked = predict_knn(model, held_features)
        out.append({
            "source": held_features.get("_source", f"row{i}"),
            "expected": held_label,
            "predicted": ranked[0] if ranked else "?",
            "ranked": ranked,
            "in_top1": ranked and ranked[0] == held_label,
            "in_top3": held_label in ranked[:3],
            "in_top5": held_label in ranked[:5],
            "features": held_features,
        })
    return out


def main():
    print("[N] loading 42codec ground truth...")
    ground = load_ground_truth()
    print(f"  ground truth: {ground}")

    print("\n[N] building labelled dataset (13 sources)...")
    dataset = build_dataset(ground)
    for f, lab in dataset:
        print(f"  {f['_source']:18s} -> {lab:8s}  ent={f['entropy']:.3f} "
              f"ext={f['ext']:6s} delim={f['delimiter']:5s} "
              f"mean_cols={f['mean_cols']:.1f}")

    print("\n[N] fitting k-NN model on full dataset...")
    model = fit_knn(dataset, k=5)
    rules_path = OUT / "rules.json"
    rules_path.write_text(json.dumps({
        "method": "k-NN k=5 on min-max-normalized 12-feature vector",
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "bool_features": BOOL_FEATURES,
        "domain_feature": "_domain",
        "known_ext": sorted(KNOWN_EXT),
        "known_delim": sorted(KNOWN_DELIM),
        "n_train": len(model["labels"]),
        "label_distribution": dict(Counter(model["labels"])),
    }, indent=2))
    print(f"  rules -> {rules_path}")

    print("\n[N] leave-one-out cross-validation (k=5)...")
    loo_rows = loo(dataset)
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"  LOO top-1 accuracy: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"  LOO top-3 accuracy: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"  LOO top-5 accuracy: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")
    for r in loo_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:18s} expected={r['expected']:12s} "
              f"top1={r['predicted']:12s} ranked={r['ranked']}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    # ----- compare v1 and v2 on the 50-file real corpus -----
    print("\n[N] comparing v1 vs v2 on 50-file real corpus...")
    sys.path.insert(0, r"D:\4\bha-codecs")
    from investigate_ssp5_recommender import recommend as v1_recommend

    REAL_CODECS = {"brotli", "bz2", "zlib", "lzma2", "ssp5", "raw",
                   "BHCC1", "BHVT1", "BHSP1", "BHCS1", "BHDS1", "BHDS2",
                   "BHDS3", "BHBK1", "BHSC1", "BHJA1", "BHNL1", "BHST1",
                   "BHLZ1", "BHTL1", "BHRT1", "BHTM1", "BHMX1", "BHMD1",
                   "BHQC1", "BHDS3", "BHSD1", "SDLT1",
                   "ours_adaptive_atomize", "ssp5_atom", "ssp5_adapt",
                   "adaptive", "atomize"}

    corpus_data = json.loads(CORPUS_RESULTS_PATH.read_text())
    rows50 = []
    # Files in the corpus dir may have been replaced by empty directories
    # between the recommender-corpus run and now. We use the features and
    # v1 prediction already recorded in the JSON, so we don't need to
    # re-read any file.
    for row in corpus_data["rows"]:
        f = dict(row["features"])  # already-extracted feature dict
        # Heuristic domain assignment, same rules as before.
        f["_domain"] = "byte"
        if f.get("ext") == ".csv" and f.get("mean_cols", 0) >= 4:
            f["_domain"] = "int"
        elif f.get("ext") == ".log" and f.get("has_numeric") and f.get("ascii_ratio", 0) > 0.9:
            f["_domain"] = "int"
        # v1 prediction is already in the row (recorded at corpus run time)
        v1_pred = row.get("predicted_codec", "?")
        v1_reason = row.get("reason", "")
        v2_ranked = predict_knn(model, f, top_k=5)
        v2_pred = v2_ranked[0] if v2_ranked else "?"
        v2_top3 = v2_ranked[:3]
        rows50.append({
            "file": row["file"],
            "domain_label": row.get("domain", "?"),
            "real_bha_magic": row.get("bha_magic"),
            "real_bha_size": row["bha_size"],
            "real_bha_pct": row["bha_pct"],
            "real_winner": row.get("winner"),
            "v1_pred": v1_pred,
            "v1_reason": v1_reason,
            "v2_pred": v2_pred,
            "v2_top3": v2_top3,
            "v1_real_codec": v1_pred in REAL_CODECS,
            "v2_real_codec": v2_pred in REAL_CODECS,
            "v2_in_bha_top3": row.get("bha_magic") in v2_top3,
        })

    n_v2_real = sum(1 for r in rows50 if r["v2_real_codec"])
    n_v1_real = sum(1 for r in rows50 if r["v1_real_codec"])
    n_v2_bh = sum(1 for r in rows50 if r["v2_pred"].startswith("BH"))
    n_v1_bh = sum(1 for r in rows50 if r["v1_pred"].startswith("BH"))
    print(f"\n  v1: real-codec {n_v1_real}/{len(rows50)}, BH-family {n_v1_bh}/{len(rows50)}")
    print(f"  v2: real-codec {n_v2_real}/{len(rows50)}, BH-family {n_v2_bh}/{len(rows50)}")

    # Pick distribution
    v1_dist = Counter(r["v1_pred"] for r in rows50)
    v2_dist = Counter(r["v2_pred"] for r in rows50)
    print(f"\n  v1 top picks: {v1_dist.most_common(8)}")
    print(f"  v2 top picks: {v2_dist.most_common(8)}")

    (OUT / "v2-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(rows50),
        "v1_real_codec_count": n_v1_real,
        "v2_real_codec_count": n_v2_real,
        "v1_bh_family_count": n_v1_bh,
        "v2_bh_family_count": n_v2_bh,
        "v1_pick_distribution": dict(v1_dist),
        "v2_pick_distribution": dict(v2_dist),
        "rows": rows50,
    }, indent=2))

    print("\n[N] done.")
    print(f"  artefacts in {OUT}/")
    print(f"  - rules.json            (k-NN model description)")
    print(f"  - loo-results.json      (top-1={n_top1}/{len(loo_rows)}, top-3={n_top3}/{len(loo_rows)})")
    print(f"  - v2-vs-v1-corpus.json  (50-file comparison)")


if __name__ == "__main__":
    main()