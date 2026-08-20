"""Investigation Q: SSP5 codec recommender v6 — adds preprocessor-aware codecs.

v5 (BHA-envelope size model) plateaued because every BH* codec has the
same inner LZMA2 layer as plain lzma2 + a 5-15 byte envelope header.
BHA's real wins on the 50-file corpus (BHNL1, BHJA1, BHQC1, BHCS1, BHRT1)
must come from preprocessor passes that run before LZMA2 inside the
envelope. Concretely:

  BHCS1 (column-store)  = transpose CSV columns before LZMA2
  BHRT1 (repeating txt) = dedup identical lines before LZMA2
  BHJA1 (JSON-aware)    = extract keys/values separately, then LZMA2
  BHQC1 (quasi-deflate) = delta + LZMA2 (or LZMA2 + Huffman)
  BHNL1 (NUL-separated) = split on NUL, sort, then LZMA2

v6 implements 4 preprocessors, applies each to every source, picks the
smallest (preprocessor × envelope-magic) combination per source, and uses
the winner as the training label for the k-NN recommender.

Preprocessors (lossless on roundtrip; pre-encoded header tells decoder
  which preprocessor to undo):
  - pp_delta       : int8/16/32/64 delta-encoding of numeric streams
  - pp_transpose   : split CSV by delimiter, interleave column-by-column
  - pp_dedup_lines : emit unique lines + back-references (line LZ77)
  - pp_json_extract: split JSON object/array into keys + values

After preprocessor, payload is LZMA2-compressed and framed with the
chosen BHA magic. We measure size only; decoder is not implemented (this
is a recommender, not a codec).

Output:
  D:\4\bha-codecs\benchmark\ssp5-recommender-v6\
    rules.json, loo-results.json, v6-vs-v1-corpus.json
"""
from __future__ import annotations

import bz2
import json
import lzma
import random
import re
import sys
import zlib
from collections import Counter
from pathlib import Path

import brotli

sys.path.insert(0, r"D:\4\bha-codecs")

# v5 sources and helpers
from investigate_ssp5_recommender_v5 import (
    gen_v3_sources, gen_v4_sources, _uleb, _lzma2_best, bha_envelope,
    BHA_FILE_MAGICS, REAL_CODECS, CORPUS_RESULTS_PATH,
)
from investigate_ssp5_recommender_v2 import (
    features_from_path, _feat_dict, Normalizer, _l1,
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, BOOL_FEATURES,
)
from investigate_ssp5_recommender_v4 import CODECS as V4_CODECS


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v6")
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp_sources"
TMP.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Preprocessors (lossless; emit a 1-byte tag so decoder can pick inverse)
# ---------------------------------------------------------------------------
PP_DELTA = 0x01
PP_TRANSPOSE = 0x02
PP_DEDUP_LINES = 0x03
PP_JSON_EXTRACT = 0x04


def pp_identity(data: bytes) -> bytes:
    return data


def pp_delta(data: bytes) -> bytes:
    """int8 delta-encode (works on byte stream; wrap on overflow).

    Each output byte = (curr - prev) mod 256. Reduces high-frequency content.
    For random bytes this is identity; for monotonically-changing streams
    it concentrates values near zero.
    """
    if len(data) < 2:
        return data
    out = bytearray(len(data))
    out[0] = data[0]
    prev = data[0]
    for i in range(1, len(data)):
        out[i] = (data[i] - prev) & 0xFF
        prev = data[i]
    return bytes(out)


def pp_delta_i64(data: bytes) -> bytes:
    """i64 little-endian delta encoding (assumes 8-byte aligned)."""
    import struct
    n = len(data) // 8
    if n < 2:
        return data
    vals = list(struct.unpack("<" + "q" * n, data[:n * 8]))
    deltas = [vals[0]] + [vals[i] - vals[i - 1] for i in range(1, n)]
    return b"".join(struct.pack("<q", v) for v in deltas)


def pp_transpose(data: bytes) -> bytes:
    """Column-store transpose of CSV/TSV: pick best delimiter, split rows,
    emit each column as its own block (delimiter-terminated)."""
    # Auto-detect delimiter
    delim = max((("csv", data.count(b",")),
                 ("tsv", data.count(b"\t")),
                 ("pipe", data.count(b"|"))),
                key=lambda x: x[1])[0]
    if delim == "csv":
        sep = b","
    elif delim == "tsv":
        sep = b"\t"
    else:
        sep = b"|"
    if data.count(sep) < 5:
        return data  # not columnar enough
    rows = data.split(b"\n")
    rows = [r for r in rows if r]
    if len(rows) < 2:
        return data
    cols = []
    ncols = max(r.count(sep) + 1 for r in rows)
    for ci in range(ncols):
        col = []
        for r in rows:
            cells = r.split(sep)
            if ci < len(cells):
                col.append(cells[ci])
        cols.append(sep.join(col))
    return b"\n".join(cols) + b"\n"


def pp_dedup_lines(data: bytes) -> bytes:
    """Emit unique lines + back-references (line-level LZ77).

    Format:
      [tag 1B][n_lines u32][u32 n_unique][u32 n_refs]
      then (u32 line_len | u32 back_ref_idx) repeated n_unique+n_refs times
      then concatenated unique lines.
    """
    lines = data.split(b"\n")
    if len(lines) < 4:
        return data
    seen: dict[int, int] = {}
    unique_blobs = []
    refs = []
    for ln in lines:
        h = hash(ln)
        if h in seen:
            refs.append(seen[h])
        else:
            idx = len(unique_blobs)
            seen[h] = idx
            unique_blobs.append(ln)
            refs.append(idx)
    # Header
    header = bytearray()
    header.append(PP_DEDUP_LINES)
    header.extend(len(lines).to_bytes(4, "little"))
    header.extend(len(unique_blobs).to_bytes(4, "little"))
    header.extend(len(refs).to_bytes(4, "little"))
    # Refs table: each ref is u32
    refs_bytes = b"".join(r.to_bytes(4, "little") for r in refs)
    # Unique lines: length-prefixed
    blobs_bytes = b"".join(len(bl).to_bytes(4, "little") + bl for bl in unique_blobs)
    return bytes(header) + refs_bytes + blobs_bytes


def pp_json_extract(data: bytes) -> bytes:
    """Naive JSON split: pull every "key": "value" pair into a separate block.

    Useful for JSON files where keys repeat heavily across records.
    """
    pairs = re.findall(rb'"([^"]+)":\s*("[^"]*"|null|true|false|-?\d+(?:\.\d+)?)',
                       data)
    if len(pairs) < 4:
        return data
    keys = b"\n".join(k for k, _ in pairs) + b"\n"
    vals = b"\n".join(v for _, v in pairs) + b"\n"
    return bytes([PP_JSON_EXTRACT]) + keys + vals


PREPROCESSORS = {
    "identity":     pp_identity,
    "delta":        pp_delta,
    "delta_i64":    pp_delta_i64,
    "transpose":    pp_transpose,
    "dedup_lines":  pp_dedup_lines,
    "json_extract": pp_json_extract,
}


# ---------------------------------------------------------------------------
# Codec registry: stdlib codecs + raw envelopes + pp+envelope combos.
# Each combo is named "BHXX__<pp>" so we can identify which combo wins.
# ---------------------------------------------------------------------------
def build_codec_registry():
    """Return {name: encoder} dict covering all (envelope, preprocessor) pairs."""
    reg = {}
    # 1. stdlib codecs (no preprocessor; v5 already had these)
    reg["brotli"] = (lambda d: brotli.compress(d, quality=11), brotli.decompress)
    reg["bz2"] = (lambda d: bz2.compress(d, 9), bz2.decompress)
    reg["zlib"] = (lambda d: zlib.compress(d, 9), zlib.decompress)
    reg["lzma2"] = (lambda d: _lzma2_best(d),
                    lambda d: lzma.decompress(d, format=lzma.FORMAT_RAW,
                                              filters=[{"id": lzma.FILTER_LZMA2}]))
    reg["raw"] = (lambda d: d, lambda d: d)
    # 2. raw BHA envelopes (no preprocessor; v5 had these)
    for name, (magic, _domain) in BHA_FILE_MAGICS.items():
        def _make_enc(m):
            return lambda d: bha_envelope(m, d)
        reg[name] = (_make_enc(magic), None)
    # 3. preprocessor + envelope combos — only the most useful ones
    useful_pp = ["delta", "delta_i64", "transpose", "dedup_lines", "json_extract"]
    useful_envelopes = [
        "BHCC1", "BHCS1", "BHVT1", "BHSC1", "BHRT1",
        "BHNL1", "BHJA1", "BHBK1", "BHDS1", "BHDS2",
    ]
    for env_name in useful_envelopes:
        magic, _ = BHA_FILE_MAGICS[env_name]
        for pp_name in useful_pp:
            pp_fn = PREPROCESSORS[pp_name]
            combo_name = f"{env_name}__{pp_name}"
            def _make_combo(pp, m, n):
                def _enc(d):
                    preprocessed = pp(d)
                    return bha_envelope(m, preprocessed)
                return _enc
            reg[combo_name] = (_make_combo(pp_fn, magic, combo_name), None)
    return reg


# ---------------------------------------------------------------------------
# Source generators (re-export from v5)
# ---------------------------------------------------------------------------
def gen_all_sources():
    """Yield (name, bytes, ext, domain) for all 37 sources."""
    yield from gen_v3_sources()
    yield from gen_v4_sources()


# ---------------------------------------------------------------------------
# Measure best (codec, preprocessor) combo per source
# ---------------------------------------------------------------------------
def measure_all(data: bytes, registry: dict) -> tuple[str, int, dict]:
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
    registry = build_codec_registry()
    n_bh = sum(1 for n in registry if n.startswith("BH"))
    n_combo = sum(1 for n in registry if "__" in n)
    print(f"[Q] codec registry: {len(registry)} codecs "
          f"({n_bh} BHA envelopes, {n_combo} pp+envelope combos, "
          f"{len(V4_CODECS)} stdlib)")

    rows = []
    print(f"\n[Q] measuring all sources against full registry...")
    for src_name, data, ext, domain in gen_all_sources():
        path = TMP / (src_name + ext)
        path.write_bytes(data)
        f = features_from_path(path)
        f["_source"] = src_name
        f["_domain"] = domain
        best, best_sz, sizes = measure_all(data, registry)
        sorted_sizes = sorted(
            [(n, s) for n, s in sizes.items() if s is not None], key=lambda x: x[1]
        )[:5]
        ratio = 100 * best_sz / len(data)
        top5_str = ", ".join(f"{n}={s}" for n, s in sorted_sizes)
        print(f"  {src_name:24s} ext={ext:6s} ent={f['entropy']:.3f} "
              f"best={best:18s} ({ratio:.2f}%)  [{top5_str}]")
        rows.append((f, best))

    feats = [f for f, _ in rows]
    labels = [lab for _, lab in rows]
    weights = [1.0] * len(rows)
    print(f"\n[Q] combined: {len(feats)} sources, "
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
def main():
    feats, labels, weights = build_extended_dataset()
    print(f"\n[Q] fitting k-NN on {len(feats)} sources "
          f"({len(set(labels))} codecs)...")
    model = fit_knn_weighted(feats, labels, weights)

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN, distance-weighted vote, sample weight=1.0",
        "training_set": f"{len(feats)} sources x {len(build_codec_registry())} codecs",
        "preprocessors": list(PREPROCESSORS.keys()),
        "total_sources": len(feats),
        "unique_codecs": len(set(labels)),
        "label_distribution": dict(Counter(labels)),
    }, indent=2))

    print(f"\n[Q] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_by_source(feats, labels, weights)
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"  LOO top-1: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"  LOO top-3: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"  LOO top-5: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")
    for r in loo_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:24s} expected={r['expected']:20s} "
              f"top1={r['top1']:20s} ranked={r['ranked'][:5]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    print(f"\n[Q] 50-file real corpus eval...")
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
        v6_ranked = predict_knn_weighted(model, f, top_k=5)
        v6_pred = v6_ranked[0] if v6_ranked else "?"
        rows50.append({
            "file": row["file"],
            "real_bha_magic": row.get("bha_magic"),
            "real_bha_size": row["bha_size"],
            "real_bha_pct": row["bha_pct"],
            "v1_pred": v1_pred,
            "v6_pred": v6_pred,
            "v6_top5": v6_ranked[:5],
            "v1_real_codec": v1_pred in REAL_CODECS,
            "v6_real_codec": v6_pred in REAL_CODECS,
            "v6_in_bha_top5": row.get("bha_magic") in v6_ranked[:5],
            "v6_matches_bha": row.get("bha_magic") == v6_pred,
        })

    n_v6_real = sum(1 for r in rows50 if r["v6_real_codec"])
    n_v1_real = sum(1 for r in rows50 if r["v1_real_codec"])
    n_v6_bh = sum(1 for r in rows50 if r["v6_pred"].startswith("BH"))
    n_v1_bh = sum(1 for r in rows50 if r["v1_pred"].startswith("BH"))
    n_v6_top5 = sum(1 for r in rows50 if r["v6_in_bha_top5"])
    n_v6_exact = sum(1 for r in rows50 if r["v6_matches_bha"])
    print(f"  v1: real={n_v1_real}/{len(rows50)}, BH={n_v1_bh}/{len(rows50)}")
    print(f"  v6: real={n_v6_real}/{len(rows50)}, BH={n_v6_bh}/{len(rows50)}, "
          f"BHA magic in top-5 = {n_v6_top5}/{len(rows50)}, "
          f"exact match = {n_v6_exact}/{len(rows50)}")

    v1_dist = Counter(r["v1_pred"] for r in rows50)
    v6_dist = Counter(r["v6_pred"] for r in rows50)
    print(f"  v1 dist: {v1_dist.most_common(8)}")
    print(f"  v6 dist: {v6_dist.most_common(8)}")

    (OUT / "v6-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(rows50),
        "v1_real_codec_count": n_v1_real,
        "v6_real_codec_count": n_v6_real,
        "v1_bh_family_count": n_v1_bh,
        "v6_bh_family_count": n_v6_bh,
        "v6_bha_magic_in_top5": n_v6_top5,
        "v6_exact_bha_match": n_v6_exact,
        "v1_pick_distribution": dict(v1_dist),
        "v6_pick_distribution": dict(v6_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[Q] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()