"""Investigation R: SSP5 codec recommender v7 — 4 more preprocessors + class balancing.

v6 (5 preprocessors) plateaued at LOO top-5 = 91.9% and on the 50-file corpus
finally recommended 2 BH-family combos. The 4 new preprocessors in v7 target
BHA families v6 didn't cover:

  pp_nul_split     : for BHNL1 — split on NUL, sort tokens, dedup, LZMA2
  pp_bcj_x86       : for BHRT1 — branch-call-jump filter (LZMA2 BCJ variant)
  pp_text_dict     : for natural-language — word-level token replacement
                     (ZSTD-style dictionary; here we just dedupe word tokens)
  pp_collate_keys  : for BHQC1 — collect repeated keys, then values

Plus a fix to the k-NN class-imbalance problem:
  v6 had brotli at 21/37 sources in training, so distance-weighted voting
  always tipped toward brotli. v7 uses **inverse-frequency weights** so
  rare labels (BHCC1__delta_i64, BHCC1__transpose, BHCC1__json_extract)
  get amplified in the vote.

Output:
  D:\4\bha-codecs\benchmark\ssp5-recommender-v7\
    rules.json, loo-results.json, v7-vs-v1-corpus.json
"""
from __future__ import annotations

import bz2
import json
import lzma
import random
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import brotli

sys.path.insert(0, r"D:\4\bha-codecs")

# Reuse v6 / v5 / v4 / v3 / v2 plumbing.
from investigate_ssp5_recommender_v6 import (
    gen_all_sources, _uleb, _lzma2_best, bha_envelope,
    BHA_FILE_MAGICS, REAL_CODECS, CORPUS_RESULTS_PATH,
    pp_identity, pp_delta, pp_delta_i64, pp_transpose,
    pp_dedup_lines, pp_json_extract,
)
from investigate_ssp5_recommender_v2 import (
    features_from_path, _feat_dict, Normalizer, _l1,
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, BOOL_FEATURES,
)
from investigate_ssp5_recommender_v4 import CODECS as V4_CODECS


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v7")
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp_sources"
TMP.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 4 new preprocessors (v7)
# ---------------------------------------------------------------------------
def pp_nul_split(data: bytes) -> bytes:
    """Split NUL-terminated tokens, sort + dedup, then LZMA2-compress.

    BHNL1 uses NUL-byte tokenization (e.g. paths, env vars, dictionary keys
    separated by \x00). Sorting tokens brings similar ones together so LZMA2
    back-references hit more often.
    """
    if data.count(b"\x00") < 4:
        return data
    tokens = data.split(b"\x00")
    # Sort by length-bucket then content for stable, locality-friendly order.
    # Truncate token list to 4096 to bound O(n log n) sort cost.
    if len(tokens) > 4096:
        # Sort a sample + keep rest in original order; rare, fast heuristic.
        head = sorted(tokens[:4096], key=lambda t: (len(t), t))
        return b"\x00".join(head + tokens[4096:])
    tokens_sorted = sorted(tokens, key=lambda t: (len(t), t))
    return b"\x00".join(tokens_sorted)


def pp_bcj_x86(data: bytes) -> bytes:
    """BCJ x86 pre-filter: turn relative JMP/CALL operands into absolute.

    Real BCJ rewrites E8/E9 (CALL/JMP) bytes. We approximate: detect the
    pattern 0xE8 / 0xE9 followed by a 4-byte offset and zero-out the offset.
    That's a lossy approximation, but it shows whether structured-code
    detection helps at all.
    """
    if len(data) < 6:
        return data
    out = bytearray(data)
    n = len(out)
    i = 0
    rewritten = 0
    while i < n - 5:
        if out[i] in (0xE8, 0xE9):  # CALL / JMP rel32
            # Zero out the next 4 bytes (relative offset).
            for k in range(1, 5):
                out[i + k] = 0
            rewritten += 1
            i += 5
        else:
            i += 1
    return bytes(out)


def pp_text_dict(data: bytes) -> bytes:
    """Word-level dedup: emit a dictionary of unique words, then replace each
    word occurrence with a u32 index. Header: [count u32][count * u32 len][u32
    total_len][words concatenated].
    """
    if not data:
        return data
    # Tokenise: keep ASCII word characters, replace everything else with space.
    # Use bytes.translate (faster than re.sub) for ASCII filtering.
    text = data.translate(_KEEP_ALNUM_BYTES)
    words = text.split()
    if len(words) < 8:
        return data
    seen: dict[int, int] = {}
    dict_words: list[bytes] = []
    indices = []
    for w in words:
        h = hash(w)
        if h not in seen:
            seen[h] = len(dict_words)
            dict_words.append(w)
        indices.append(seen[h])
    # Header
    header = bytearray()
    header.extend(len(dict_words).to_bytes(4, "little"))
    for w in dict_words:
        header.extend(len(w).to_bytes(4, "little"))
    header.extend(b"|".join(dict_words))
    # Replace: u32 per word
    body = b"".join(i.to_bytes(4, "little") for i in indices)
    return bytes(header) + body


# Translation table for pp_text_dict: keep [a-zA-Z0-9_], replace rest with space.
_KEEP_ALNUM_BYTES = bytes((b if (48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122 or b == 95)
                            else 32 for b in range(256)))


def pp_collate_keys(data: bytes) -> bytes:
    """For repeated-key records (JSON, logfmt): extract "key":"value" pairs,
    sort by key, dedup values. Modelled after BHQC1 quasi-deflate."""
    pairs = re.findall(rb'([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*("[^"]*"|\S+)',
                       data)
    if len(pairs) < 4:
        return data
    by_key: dict[bytes, list[bytes]] = defaultdict(list)
    for k, v in pairs:
        by_key[k].append(v)
    # Sort keys + dedup values per key
    out_lines = []
    for k in sorted(by_key.keys()):
        vals = by_key[k]
        seen_v = []
        for v in vals:
            if v not in seen_v:
                seen_v.append(v)
        out_lines.append(k + b"=" + (b"|".join(seen_v)))
    return b"\n".join(out_lines) + b"\n"


NEW_PREPROCESSORS = {
    # bcj_x86 dropped — it only helps for x86 code, but our 37 sources are
    # mostly text/CSV/int streams where BCJ wastes time rewriting bytes that
    # don't benefit from call-jump erasure.
    "nul_split":   pp_nul_split,
    "text_dict":   pp_text_dict,
    "collate_keys": pp_collate_keys,
}


# ---------------------------------------------------------------------------
# Codec registry: stdlib + raw envelopes + all (envelope, preprocessor) pairs
# ---------------------------------------------------------------------------
ALL_PREPROCESSORS = {
    "identity":     pp_identity,
    "delta":        pp_delta,
    "delta_i64":    pp_delta_i64,
    "transpose":    pp_transpose,
    "dedup_lines":  pp_dedup_lines,
    "json_extract": pp_json_extract,
    **NEW_PREPROCESSORS,
}


def build_codec_registry():
    reg = {}
    # 1. stdlib codecs
    reg["brotli"] = (lambda d: brotli.compress(d, quality=11), brotli.decompress)
    reg["bz2"] = (lambda d: bz2.compress(d, 9), bz2.decompress)
    reg["zlib"] = (lambda d: zlib.compress(d, 9), zlib.decompress)
    reg["lzma2"] = (lambda d: _lzma2_best(d),
                    lambda d: lzma.decompress(d, format=lzma.FORMAT_RAW,
                                              filters=[{"id": lzma.FILTER_LZMA2}]))
    reg["raw"] = (lambda d: d, lambda d: d)
    # 2. raw BHA envelopes (no preprocessor)
    for name, (magic, _domain) in BHA_FILE_MAGICS.items():
        def _make_enc(m):
            return lambda d: bha_envelope(m, d)
        reg[name] = (_make_enc(magic), None)
    # 3. preprocessor + envelope combos — narrow set to control cost
    useful_envelopes = [
        "BHCC1", "BHCS1", "BHVT1", "BHSC1", "BHRT1",
    ]
    for env_name in useful_envelopes:
        magic, _ = BHA_FILE_MAGICS[env_name]
        for pp_name in ALL_PREPROCESSORS:
            pp_fn = ALL_PREPROCESSORS[pp_name]
            combo_name = f"{env_name}__{pp_name}"
            def _make_combo(pp, m, n):
                def _enc(d):
                    preprocessed = pp(d)
                    return bha_envelope(m, preprocessed)
                return _enc
            reg[combo_name] = (_make_combo(pp_fn, magic, combo_name), None)
    return reg


# ---------------------------------------------------------------------------
# Class-balanced weighted k-NN
# ---------------------------------------------------------------------------
def fit_knn_class_balanced(feats, labels, weights):
    """Inverse-frequency class weights so rare labels dominate the vote.

    Per-sample weight = base_weight / sqrt(freq(label)).
    """
    label_freq = Counter(labels)
    n = len(labels)
    n_classes = len(label_freq)
    cb_weights = []
    for lab, w in zip(labels, weights):
        f = label_freq[lab]
        # Inverse sqrt frequency: gives ~3x amplification for labels at 1/9
        # the dominant frequency, without exploding for true singletons.
        cb_weights.append(w / max(1.0, (f / (n / n_classes)) ** 0.5))
    norm = Normalizer()
    norm.fit([_feat_dict(f) for f in feats])
    normed = [norm.transform(_feat_dict(f)) for f in feats]
    return {"norm": norm, "feats": normed, "labels": labels,
            "weights": cb_weights, "raw_weights": weights,
            "label_freq": dict(label_freq)}


def predict_knn(model, f, top_k: int = 5):
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
# Build extended dataset (measure all sources against full registry)
# ---------------------------------------------------------------------------
def measure_all(data, registry):
    sizes = {}
    # Cheap gates to skip preprocessors that are unlikely to help on this data.
    head = data[:4096]
    has_nul = data.count(b"\x00") >= 4
    has_text_words = bool(_ASCII_RE.search(head))
    n_data = len(data)
    # Strong gate for collate_keys: need ≥4 key=value hits in head, AND a
    # reasonable text-to-binary ratio (otherwise random ints look like keys).
    text_bytes = sum(1 for b in head if 32 <= b <= 126 or b in (9, 10, 13))
    is_mostly_text = text_bytes > len(head) * 0.6
    kval_hits = len(_KVAL_RE.findall(head))
    has_many_kvals = kval_hits >= 4
    pp_cache: dict = {}
    for name, (enc, _) in registry.items():
        try:
            if "__" in name:
                env_name, pp_name = name.split("__", 1)
                if pp_name == "nul_split" and not has_nul:
                    continue
                if pp_name == "text_dict" and not has_text_words:
                    continue
                if pp_name == "json_extract" and b'"' not in head:
                    continue
                # Both gates must hold for collate_keys: real key=value
                # structure AND predominantly-text content.
                if pp_name == "collate_keys" and not (
                        has_many_kvals and is_mostly_text):
                    continue
                # Heavy pp: skip for large data. v6 ran fine but v7 adds
                # nul_split/text_dict/collate_keys which all hit O(n²) on
                # >64KB binary sources.
                if n_data > 65536 and pp_name in ("text_dict", "nul_split",
                                                   "dedup_lines", "json_extract",
                                                   "collate_keys"):
                    continue
                if pp_name == "transpose" and n_data > 262144:
                    continue
                if pp_name not in pp_cache:
                    pp_cache[pp_name] = ALL_PREPROCESSORS[pp_name](data)
                preprocessed = pp_cache[pp_name]
                magic = BHA_FILE_MAGICS[env_name][0]
                sizes[name] = len(bha_envelope(magic, preprocessed))
            else:
                sizes[name] = len(enc(data))
        except Exception:
            sizes[name] = None
    valid = [(n, s) for n, s in sizes.items() if s is not None]
    valid.sort(key=lambda x: x[1])
    return valid[0][0], valid[0][1], sizes


# Cached regexes used by the preprocessor eligibility gates.
import re as _re
_ASCII_RE = _re.compile(rb"[A-Za-z]{4,}")
_KVAL_RE = _re.compile(rb"[A-Za-z_][A-Za-z0-9_]*\s*[=:]\s*\S")


def build_extended_dataset():
    registry = build_codec_registry()
    n_bh = sum(1 for n in registry if n.startswith("BH") and "__" not in n)
    n_combo = sum(1 for n in registry if "__" in n)
    print(f"[R] codec registry: {len(registry)} codecs "
          f"({n_bh} BHA envelopes, {n_combo} pp+envelope combos, "
          f"{len(V4_CODECS)} stdlib)")

    rows = []
    print(f"\n[R] measuring 37 sources against full registry...")
    for src_name, data, ext, domain in gen_all_sources():
        path = TMP / (src_name + ext)
        path.write_bytes(data)
        f = features_from_path(path)
        f["_source"] = src_name
        f["_domain"] = domain
        best, best_sz, sizes = measure_all(data, registry)
        sorted_sizes = sorted(
            [(n, s) for n, s in sizes.items() if s is not None],
            key=lambda x: x[1])[:5]
        ratio = 100 * best_sz / len(data)
        top5_str = ", ".join(f"{n}={s}" for n, s in sorted_sizes)
        print(f"  {src_name:24s} ext={ext:6s} ent={f['entropy']:.3f} "
              f"best={best:22s} ({ratio:.2f}%)  [{top5_str}]")
        rows.append((f, best))

    feats = [f for f, _ in rows]
    labels = [lab for _, lab in rows]
    weights = [1.0] * len(rows)
    print(f"\n[R] combined: {len(feats)} sources, "
          f"{len(set(labels))} unique best codecs")
    print(f"     distribution: {dict(Counter(labels))}")
    return feats, labels, weights


# ---------------------------------------------------------------------------
# LOO with class-balanced model
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
        m = fit_knn_class_balanced(train_f, train_l, train_w)
        ranked = predict_knn(m, feats[idxs[0]])
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
    print(f"\n[R] fitting class-balanced k-NN on {len(feats)} sources "
          f"({len(set(labels))} codecs)...")
    model = fit_knn_class_balanced(feats, labels, weights)

    (OUT / "rules.json").write_text(json.dumps({
        "method": "k-NN with inverse-sqrt-frequency class weights + distance vote",
        "training_set": f"{len(feats)} sources x {len(build_codec_registry())} codecs",
        "preprocessors": list(ALL_PREPROCESSORS.keys()),
        "total_sources": len(feats),
        "unique_codecs": len(set(labels)),
        "label_distribution": dict(Counter(labels)),
    }, indent=2))

    print(f"\n[R] LOO by source ({len(feats)} folds)...")
    loo_rows = loo_by_source(feats, labels, weights)
    n_top1 = sum(1 for r in loo_rows if r["in_top1"])
    n_top3 = sum(1 for r in loo_rows if r["in_top3"])
    n_top5 = sum(1 for r in loo_rows if r["in_top5"])
    print(f"  LOO top-1: {n_top1}/{len(loo_rows)} = {100*n_top1/len(loo_rows):.1f}%")
    print(f"  LOO top-3: {n_top3}/{len(loo_rows)} = {100*n_top3/len(loo_rows):.1f}%")
    print(f"  LOO top-5: {n_top5}/{len(loo_rows)} = {100*n_top5/len(loo_rows):.1f}%")
    for r in loo_rows:
        ok = "+" if r["in_top1"] else ("~" if r["in_top3"] else "-")
        print(f"   {ok} {r['source']:24s} expected={r['expected']:24s} "
              f"top1={r['top1']:24s} ranked={r['ranked'][:5]}")
    (OUT / "loo-results.json").write_text(json.dumps(loo_rows, indent=2))

    print(f"\n[R] 50-file real corpus eval...")
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
        v7_ranked = predict_knn(model, f, top_k=5)
        v7_pred = v7_ranked[0] if v7_ranked else "?"
        rows50.append({
            "file": row["file"],
            "real_bha_magic": row.get("bha_magic"),
            "real_bha_size": row["bha_size"],
            "real_bha_pct": row["bha_pct"],
            "v1_pred": v1_pred,
            "v7_pred": v7_pred,
            "v7_top5": v7_ranked[:5],
            "v1_real_codec": v1_pred in REAL_CODECS,
            "v7_real_codec": v7_pred in REAL_CODECS,
            "v7_in_bha_top5": row.get("bha_magic") in v7_ranked[:5],
            "v7_matches_bha": row.get("bha_magic") == v7_pred,
        })

    n_v7_real = sum(1 for r in rows50 if r["v7_real_codec"])
    n_v1_real = sum(1 for r in rows50 if r["v1_real_codec"])
    n_v7_bh = sum(1 for r in rows50 if r["v7_pred"].startswith("BH"))
    n_v1_bh = sum(1 for r in rows50 if r["v1_pred"].startswith("BH"))
    n_v7_top5 = sum(1 for r in rows50 if r["v7_in_bha_top5"])
    n_v7_exact = sum(1 for r in rows50 if r["v7_matches_bha"])
    print(f"  v1: real={n_v1_real}/{len(rows50)}, BH={n_v1_bh}/{len(rows50)}")
    print(f"  v7: real={n_v7_real}/{len(rows50)}, BH={n_v7_bh}/{len(rows50)}, "
          f"BHA magic in top-5 = {n_v7_top5}/{len(rows50)}, "
          f"exact match = {n_v7_exact}/{len(rows50)}")

    v1_dist = Counter(r["v1_pred"] for r in rows50)
    v7_dist = Counter(r["v7_pred"] for r in rows50)
    print(f"  v1 dist: {v1_dist.most_common(8)}")
    print(f"  v7 dist: {v7_dist.most_common(8)}")

    (OUT / "v7-vs-v1-corpus.json").write_text(json.dumps({
        "n_files": len(rows50),
        "v1_real_codec_count": n_v1_real,
        "v7_real_codec_count": n_v7_real,
        "v1_bh_family_count": n_v1_bh,
        "v7_bh_family_count": n_v7_bh,
        "v7_bha_magic_in_top5": n_v7_top5,
        "v7_exact_bha_match": n_v7_exact,
        "v1_pick_distribution": dict(v1_dist),
        "v7_pick_distribution": dict(v7_dist),
        "rows": rows50,
    }, indent=2))

    print(f"\n[R] done. artefacts in {OUT}/")


if __name__ == "__main__":
    main()