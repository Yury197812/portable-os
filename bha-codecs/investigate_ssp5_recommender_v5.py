"""Investigation P: SSP5 codec recommender v5 — adds BHA-envelope codecs.

v4 (extended training to 37 sources) plateaued at LOO top-1 = 56.8% but on
the 50-file real corpus still collapsed into brotli (39/50) because v4's
training set only contained 6 codecs: raw, brotli, bz2, zlib, lzma2, ssp5.
BHA on those files actually used BHNL1, BHJA1, BHQC1, BHCS1, BHRT1, BHSC1,
BHBK1, BHDS1, BHDS2, etc. — none of which v4 had in its codec registry, so
the k-NN literally could not recommend them.

v5 closes this gap. Instead of roundtrip-validating each codec (slow,
requires decoder), we use size modelling from investigate_ssp5_42codec.py:
for every codec, the encoded size is

    bha_envelope(magic, data) = magic | ULEB(orig) | ULEB(0) | u32_le(comp) | LZMA2(body)

where LZMA2(body) is the minimum over presets 6 and 9|PRESET_EXTREME.
This gives a faithful size estimate without invoking the full BHA ensemble.
The decoder doesn't matter for *recommendation* — we only need the size to
choose the smallest codec per source.

Concretely v5:
  1. Imports the 27 BHA-envelope magics from investigate_ssp5_42codec.
  2. For each of 37 sources (13 v3 + 24 v4), measures the size of each
     BHA-envelope codec + the 6 roundtrip codecs from v4.
  3. Records the best (source, codec) per source with weight 1.0.
  4. Re-fits the k-NN over the combined (feature, best_codec) set.
  5. LOO by source.
  6. 50-file corpus eval against v1, v4, v5.

Output:
  D:\4\bha-codecs\benchmark\ssp5-recommender-v5\
    rules.json, loo-results.json, v5-vs-v1-corpus.json
"""
from __future__ import annotations

import bz2
import json
import lzma
import random
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

import brotli

sys.path.insert(0, r"D:\4\bha-codecs")

# Reuse v4's source generators so we measure the *same* sources as before.
from investigate_ssp5_recommender_v4 import (
    NEW_SOURCES,
    gen_html, gen_xml, gen_yaml, gen_toml, gen_jsonl,
    gen_markdown, gen_js, gen_cyrillic, gen_mixed_binary_text,
    gen_quoted_csv, gen_semicolon_sparse, gen_tsv, gen_mixed_delim,
    gen_pipe_kv, gen_fixed_width_log, gen_numeric_csv_sparse,
    gen_numeric_csv_dense, gen_html_inline, gen_repeating_short_lines,
    gen_arithmetic_progression, gen_geometric_progression,
    gen_zero_run, gen_dense_small_ints, gen_low_entropy_text,
)

# Reuse v2's feature machinery.
from investigate_ssp5_recommender_v2 import (
    features_from_path, _feat_dict, Normalizer, _l1,
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, BOOL_FEATURES,
    KNOWN_EXT, KNOWN_DELIM,
)

# Reuse v4's reusable roundtrip codecs.
from investigate_ssp5_recommender_v4 import (
    CODECS as V4_CODECS,
    _lzma2_best,
)

# Reuse v3's 13-source corpus and generators.
from investigate_ssp5_recommender_v3 import (
    load_top5_per_source, build_augmented_dataset,
)
from investigate_ssp5_recommender_v2 import build_dataset as v2_build_dataset
from investigate_ssp5_even_atom import ssp5_encode, ssp5_decode
from investigate_ssp5_real_corpus import (
    CORPUS,
    extract_ints_dense_csv, extract_ints_telemetry,
)


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v5")
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp_sources"
TMP.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# BHA envelope helpers (copied from investigate_ssp5_42codec.py:64-95)
# ---------------------------------------------------------------------------
def _uleb(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def bha_envelope(magic: bytes, data: bytes) -> bytes:
    comp = _lzma2_best(data)
    out = bytearray(magic)
    out.extend(_uleb(len(data)))
    out.extend(_uleb(0))
    out.extend(len(comp).to_bytes(4, "little"))
    out.extend(comp)
    return bytes(out)


# BHA envelopes — same set as investigate_ssp5_42codec.py:159-187
BHA_FILE_MAGICS = {
    "BHST1":   (b"BHST1",   "byte"),
    "BHRT1":   (b"BHRT1",   "int"),
    "BHVT1":   (b"BHVT1",   "int"),
    "BHSC1":   (b"BHSC1",   "int"),
    "BHTC1":   (b"BHTC1",   "int"),
    "BHTM1":   (b"BHTM1",   "int"),
    "BHNL1":   (b"BHNL1",   "byte"),
    "BHJA1":   (b"BHJA1",   "byte"),
    "BHQC1":   (b"BHQC1",   "int"),
    "BHCS1":   (b"BHCS1",   "byte"),
    "BHMT1":   (b"BHMT1",   "int"),
    "BHSP1":   (b"BHSP1",   "byte"),
    "BHDT1":   (b"BHDT1",   "int"),
    "BHMX1":   (b"BHMX1",   "int"),
    "BHMD1":   (b"BHMD1",   "int"),
    "BHCC1":   (b"BHCC1",   "int"),
    "BHTL1":   (b"BHTL1",   "byte"),
    "BHLZ1":   (b"BHLZ1",   "byte"),
    "BHDS3":   (b"BHDS3",   "byte"),
    "BHSD1":   (b"BHSD1",   "byte"),
    "SDLT1":   (b"SDLT1",   "byte"),
    "BHBK1":   (b"BHBK1",   "byte"),
    "BHDS1":   (b"BHDS1",   "byte"),
    "BHDS2":   (b"BHDS2",   "byte"),
}


def _make_bha_enc(magic):
    def _enc(d):
        return bha_envelope(magic, d)
    return _enc


# Build the full codec registry: v4 roundtrip codecs + 24 BHA envelopes.
def build_codec_registry():
    reg = dict(V4_CODECS)
    for name, (magic, domain) in BHA_FILE_MAGICS.items():
        reg[name] = (_make_bha_enc(magic), None)  # no decoder; size only
    return reg


# ---------------------------------------------------------------------------
# The 13 v3 sources — re-derived through the same generator functions used
# in v3 so feature space matches.
# ---------------------------------------------------------------------------
def gen_v3_sources():
    """Yield (name, bytes, ext, domain) for the 13 original sources."""
    import struct
    from investigate_ssp5_even_atom import (
        gen_even_mask_zero, gen_even_mask_one,
        gen_arbitrary, gen_arbitrary_mixed,
    )
    int_synth = {
        "syn_even_0":     gen_even_mask_zero(16_384),
        "syn_even_1":     gen_even_mask_one(16_384),
        "syn_arb_lcg":    gen_arbitrary(16_384),
        "syn_arb_mixed":  gen_arbitrary_mixed(16_384),
    }
    int_real = {
        "real_csv_int":   extract_ints_dense_csv(CORPUS / "dense_numeric_csv_300k.csv", max_rows=16_384),
        "real_telem_int": extract_ints_telemetry(CORPUS / "telemetry_logs_1m.log", max_rows=16_384),
    }
    byte_sources = {
        "text_repeated":   (b"The quick brown fox jumps over the lazy dog. "
                            b"Pack my box with five dozen liquor jugs. " * 5000)[:200_000],
        "binary_zeros":    b"\x00" * 200_000,
        "binary_random":   bytes(random.Random(42).getrandbits(8) for _ in range(200_000)),
        "ini_config":      (CORPUS / "ini_config_128k.ini").read_bytes()[:100_000],
        "json_array":      (CORPUS / "data_json_100k.json").read_bytes(),
        "css_repeated":    (CORPUS / "css_repeated_150k.css").read_bytes(),
        "telem_log_raw":   (CORPUS / "telemetry_logs_1m.log").read_bytes()[:200_000],
    }
    ext_map = {
        "syn_even_0": ".csv", "syn_even_1": ".csv",
        "syn_arb_lcg": ".csv", "syn_arb_mixed": ".csv",
        "real_csv_int": ".csv", "real_telem_int": ".log",
        "text_repeated": ".txt", "binary_zeros": ".bin",
        "binary_random": ".bin", "ini_config": ".ini",
        "json_array": ".json", "css_repeated": ".css",
        "telem_log_raw": ".log",
    }
    domain_map = {
        "syn_even_0": "int", "syn_even_1": "int",
        "syn_arb_lcg": "int", "syn_arb_mixed": "int",
        "real_csv_int": "int", "real_telem_int": "int",
        "text_repeated": "byte", "binary_zeros": "byte",
        "binary_random": "byte", "ini_config": "byte",
        "json_array": "byte", "css_repeated": "byte",
        "telem_log_raw": "byte",
    }
    for name, vals in int_synth.items():
        data = b"".join(struct.pack("<q", v) for v in vals)
        yield name, data, ext_map[name], domain_map[name]
    for name, vals in int_real.items():
        data = b"".join(struct.pack("<q", v) for v in vals)
        yield name, data, ext_map[name], domain_map[name]
    for name, data in byte_sources.items():
        yield name, data, ext_map[name], domain_map[name]


def gen_v4_sources():
    """Yield (name, bytes, ext, domain) for v4 NEW_SOURCES."""
    gen_map = {
        "html": gen_html, "xml": gen_xml, "yaml": gen_yaml,
        "toml": gen_toml, "jsonl": gen_jsonl, "markdown": gen_markdown,
        "js_minified": gen_js, "cyrillic_utf8": gen_cyrillic,
        "mixed_binary_text": gen_mixed_binary_text,
        "quoted_csv": gen_quoted_csv, "semicolon_sparse": gen_semicolon_sparse,
        "tsv": gen_tsv, "mixed_delim": gen_mixed_delim, "pipe_kv": gen_pipe_kv,
        "fixed_width_log": gen_fixed_width_log,
        "numeric_csv_sparse": gen_numeric_csv_sparse,
        "numeric_csv_dense": gen_numeric_csv_dense,
        "html_inline": gen_html_inline,
        "repeating_lines": gen_repeating_short_lines,
        "arith_progression": gen_arithmetic_progression,
        "geo_progression": gen_geometric_progression,
        "zero_run_sparse": gen_zero_run,
        "dense_small_ints": gen_dense_small_ints,
        "low_entropy_text": gen_low_entropy_text,
    }
    for name, gen_fn, ext, domain in NEW_SOURCES:
        yield name, gen_fn(), ext, domain


# ---------------------------------------------------------------------------
# Measure best codec for each source across full registry
# ---------------------------------------------------------------------------
def measure_all(data: bytes, registry: dict) -> tuple[str, int, dict]:
    """Return (best_name, best_size, all_sizes)."""
    sizes = {}
    for name, (enc, _) in registry.items():
        try:
            sizes[name] = len(enc(data))
        except Exception:
            sizes[name] = None
    valid = [(n, s) for n, s in sizes.items() if s is not None]
    valid.sort(key=lambda x: x[1])
    return valid[0][0], valid[0][1], sizes


def build_extended_dataset() -> tuple[list[dict], list[str], list[float]]:
    """Measure all sources against full codec registry; return (feats, labels, w)."""
    registry = build_codec_registry()
    print(f"[P] codec registry: {len(registry)} codecs "
          f"({len([n for n in registry if n.startswith('BH')])} BHA envelopes + "
          f"{len(V4_CODECS)} stdlib)")

    rows = []  # (features, best_codec_name)
    print(f"\n[P] measuring {13 + len(NEW_SOURCES)} sources against full registry...")
    for src_name, data, ext, domain in list(gen_v3_sources()) + list(gen_v4_sources()):
        path = TMP / (src_name + ext)
        path.write_bytes(data)
        f = features_from_path(path)
        f["_source"] = src_name
        f["_domain"] = domain
        best, best_sz, sizes = measure_all(data, registry)
        # show top 3 to make the choice auditable
        sorted_sizes = sorted(
            [(n, s) for n, s in sizes.items() if s is not None], key=lambda x: x[1]
        )[:3]
        ratio = 100 * best_sz / len(data)
        top3_str = ", ".join(f"{n}={s}" for n, s in sorted_sizes)
        print(f"  {src_name:24s} ext={ext:6s} ent={f['entropy']:.3f} "
              f"best={best:8s} ({ratio:.2f}%)  top3=[{top3_str}]")
        rows.append((f, best))

    feats = [f for f, _ in rows]
    labels = [lab for _, lab in rows]
    weights = [1.0] * len(rows)
    print(f"\n[P] combined: {len(feats)} sources, "
          f"{len(set(labels))} unique best codecs")
    print(f"     distribution: {dict(Counter(labels))}")
    return feats, labels, weights


# ---------------------------------------------------------------------------
# Weighted k-NN
# ---------------------------------------------------------------------------
def fit_knn_weighted(feats, labels, weights):
    norm = Normalizer()
    norm.fit([_feat_dict(f) for f in feats])
    normed = [norm.transform(_feat_dict(f)) for f in feats]
    return {"norm": norm, "feats": normed, "labels": labels, "weights": weights}


def predict_knn_weighted(model, f, top_k: int = 5):
    norm = model["norm"]
    q = norm.transform(_feat_dict(f))
    dists = [(_l1(q, t), i) for i, t in enumerate(model["feats"])]
    dists.sort()
    eps = 1e-3
    scores = Counter()
    for d, i in dists:
        w = model["weights"][i] / (d + eps)
        scores[model["labels"][i]] += w
    return [c for c, _ in scores.most_common()]


# ---------------------------------------------------------------------------
# LOO
# ---------------------------------------------------------------------------
def loo_by_source(feats, labels, weights):
    src_of: dict[str, list[int]] = {}
    for i, f in enumerate(feats):
        src_of.setdefault(f["_source"], []).append(i)
    src_labels = {src: set(lab for i in idxs for lab in [labels[i]])
                  for src, idxs in src_of.items()}
    out = []
    for src, idxs in src_of.items():
        held = set(idxs)
        train_f = [feats[i] for i in range(len(feats)) if i not in held]
        train_l = [labels[i] for i in range(len(feats)) if i not in held]
        train_w = [weights[i] for i in range(len(feats)) if i not in held]
        if not train_f:
            continue
        m = fit_knn_weighted(train_f, train_l, train_w)
        ranked = predict_knn_weighted(m, feats[idxs[0]])
        out.append({
            "source": src,
            "expected": labels[idxs[0]],
            "ranked": ranked,
            "top1": ranked[0] if ranked else "?",
            "in_top1": ranked and ranked[0] == labels[idxs[0]],
            "in_top3": labels[idxs[0]] in ranked[:3],
            "in_top5": labels[idxs[0]] in ranked[:5],
        })
    return out


# ---------------------------------------------------------------------------
# 50-file real corpus eval
# ---------------------------------------------------------------------------
CORPUS_RESULTS_PATH = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus\corpus-results.json")
REAL_CODECS = {"brotli", "bz2", "zlib", "lzma2", "ssp5", "raw",
               *BHA_FILE_MAGICS.keys(),
               "ours_adaptive_atomize", "ssp5_atom", "ssp5_adapt",
               "adaptive", "atomize"}


def main():
    feats, labels, weights = build_extended_dataset()
    print(f"\n[P] fitting k-NN on {len(feats)} sources ({len(set(labels))} codecs)...")
    model = fit_knn_weighted(feats, labels, weights)

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN, distance-weighted vote, sample weight=1.0",
        "training_set": f"{len(feats)} sources (13 v3 + 24 v4) measured against "
                        f"{len(build_codec_registry())} codecs",
        "total_sources": len(feats),
        "unique_codecs": len(set(labels)),
        "label_distribution": dict(Counter(labels)),
        "sources": [f["_source"] for f in feats],
    }, indent=2))

    print(f"\n[P] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_by_source(feats, labels, weights)
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"  LOO top-1: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"  LOO top-3: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"  LOO top-5: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")
    for r in loo_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:24s} expected={r['expected']:8s} "
              f"top1={r['top1']:8s} ranked={r['ranked'][:5]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    print(f"\n[P] 50-file real corpus eval...")
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
        v5_ranked = predict_knn_weighted(model, f, top_k=5)
        v5_pred = v5_ranked[0] if v5_ranked else "?"
        rows50.append({
            "file": row["file"],
            "real_bha_magic": row.get("bha_magic"),
            "real_bha_size": row["bha_size"],
            "real_bha_pct": row["bha_pct"],
            "v1_pred": v1_pred,
            "v5_pred": v5_pred,
            "v5_top5": v5_ranked[:5],
            "v1_real_codec": v1_pred in REAL_CODECS,
            "v5_real_codec": v5_pred in REAL_CODECS,
            "v5_in_bha_top5": row.get("bha_magic") in v5_ranked[:5],
            "v5_matches_bha": row.get("bha_magic") == v5_pred,
        })

    n_v5_real = sum(1 for r in rows50 if r["v5_real_codec"])
    n_v1_real = sum(1 for r in rows50 if r["v1_real_codec"])
    n_v5_bh = sum(1 for r in rows50 if r["v5_pred"].startswith("BH"))
    n_v1_bh = sum(1 for r in rows50 if r["v1_pred"].startswith("BH"))
    n_v5_top5 = sum(1 for r in rows50 if r["v5_in_bha_top5"])
    n_v5_exact = sum(1 for r in rows50 if r["v5_matches_bha"])
    print(f"  v1: real={n_v1_real}/{len(rows50)}, BH={n_v1_bh}/{len(rows50)}")
    print(f"  v5: real={n_v5_real}/{len(rows50)}, BH={n_v5_bh}/{len(rows50)}, "
          f"BHA magic in top-5 = {n_v5_top5}/{len(rows50)}, "
          f"exact match = {n_v5_exact}/{len(rows50)}")

    v1_dist = Counter(r["v1_pred"] for r in rows50)
    v5_dist = Counter(r["v5_pred"] for r in rows50)
    print(f"  v1 dist: {v1_dist.most_common(8)}")
    print(f"  v5 dist: {v5_dist.most_common(8)}")

    (OUT / "v5-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(rows50),
        "v1_real_codec_count": n_v1_real,
        "v5_real_codec_count": n_v5_real,
        "v1_bh_family_count": n_v1_bh,
        "v5_bh_family_count": n_v5_bh,
        "v5_bha_magic_in_top5": n_v5_top5,
        "v5_exact_bha_match": n_v5_exact,
        "v1_pick_distribution": dict(v1_dist),
        "v5_pick_distribution": dict(v5_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[P] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()