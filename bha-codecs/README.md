# BHA SSP5 Codec Recommender

Recommender that picks the best codec per input file for the Black Hole
Archiver (BHA). Trained on a 37-source synthetic corpus + 50 real BHA
files; uses k-NN with three-layer weighting (class-balance, distance,
BHA-dominant locality).

## Stable version

**v9b** — recommended for production. Real-only LOO top-1 = 21/50 = 42%.

```bash
python investigate_ssp5_recommender_v9b.py
```

## Metrics summary (50 real BHA files, leave-one-out)

| Version | Approach | LOO top-1 | LOO top-3 | 50-file holdout |
|---------|----------|-----------|-----------|------------------|
| v1      | hand-coded decision tree (14 KB) | 14/14 overfit | — | 11/50 = 22.0% |
| v2      | k-NN baseline (13 sources) | 5/13 = 38.5% | 9/13 = 69.2% | 0/50 |
| v3      | augmented k-NN (13×5=65) | 4/13 = 30.8% | 10/13 = 76.9% | 5/50 |
| v4      | extended to 37 sources, 6 stdlib codecs | 21/37 = 56.8% | — | 0/50 |
| v5      | + 24 BHA-envelope magics (size model) | 19/37 = 51.4% | 36/37 = 97.3% | 0/50 |
| v6      | + 5 preprocessors (delta_i64 / transpose / dedup_lines / json_extract) | 18/37 = 48.6% | 29/37 = 78.4% | 2/50 |
| v7      | + nul_split / text_dict / collate_keys + class-balanced k-NN | 18/37 = 48.6% | 31/37 = 83.8% | 1/50 |
| v8      | v7 training + 50 real corpus points (bha_magic labels) | 17/50 = 34.0% | 28/50 = 56.0% | 17 hits |
| v9      | v8 + IDF locality log(1+N/df) | 15/50 = 30.0% | 25/50 = 50.0% | 15 hits |
| **v9b** | **v8 + IDF locality restricted to BHA-dominant codecs** | **21/50 = 42.0%** | **26/50 = 52.0%** | **21 hits** |

## v9b algorithm (3-layer weight)

For each query file:

1. **Feature extraction** (12 features from `features_from_path`):
   - extension (one-hot), size, entropy, zero_ratio, ascii_ratio,
   - line_len_std, has_repeated_lines, binary_repeat, has_numeric,
   - delimiter, csv_density, mean_cols, _domain (int/byte)

2. **Min-max normalization** (Normalizer) — equalize feature scales.

3. **k-NN with 3-layer weighted vote**:
   ```
   For each of 87 training points (37 synthetic + 50 real):
       d = L1 distance from query to point
       cb = 1 / sqrt(freq(label) / (n/n_classes))   # class-balance
       locality = log(1 + N/df(label)) if label in BHA_DOMINANT else 1.0
       score[label] += cb / (d + 0.001) * locality
   ```
   where:
   - `freq(label)` = global frequency of this label in training set
   - `N = 30` (k-Neigh window), `df(label)` = local document frequency
   - **BHA_DOMINANT** = curated set of BHA file_codec magics +
     preprocessor combos that BHA actually uses (lzma2, BHTC1, BHVT1,
     BHRT1, BHJA1, BHNL1, BHCC1, BHTM1, BHTL1, BHMX1, BHQC1, BHSP1,
     BHST1, BHDT1, BHCS1, BHBK1, BHDS1, BHDS2, BHCC1__delta_i64,
     BHCC1__transpose, BHCC1__json_extract, BHCC1__collate_keys,
     raw, etc.). Non-dominant labels (brotli, bz2, zlib) get locality=1.0
     (no boost).

4. **Return top-K codecs** sorted by accumulated score.

## Why v9b beats v8 and v9

v8 (no locality): top-1 = 17/50 = 34.0%. Beats v1 hand-coded 22.0% by
training on real-corpus bha_magic labels rather than synthetic-only
ground truth. But on dense feature regions, lzma2 vs brotli vs bz2
votes are tied (similar distances) and the most-common local label
wins by random tie-breaking.

v9 (raw locality): top-1 = 15/50 = 30.0%. Regresses because IDF
locality log(1+N/df) amplifies globally-rare labels (bz2 at 6/87)
within local k-NN windows — bz2 jumped from 1 to 9 picks, while
BHA never uses bz2 on these 50 files. Wrong metric.

v9b (BHA-dominant locality): top-1 = 21/50 = 42.0%. Restricts locality
amplification to BHA file_codec magics. bz2 falls back to v8-style
neutral weight (1.0), so it stops stealing lzma2 votes. BHA codecs
(BHTC1, BHVT1, BHRT1, BHJA1) still get IDF amplification when they
appear rarely in the local window — helping break ties correctly.

## v9b output

```bash
$ python investigate_ssp5_recommender_v9b.py
...
[U] real      LOO (50): top-1=21, top-3=26, top-5=30
[U] v9b 50-file holdout:
    top-1 matches: 21/50 = 42.0%
    top-3 contains: 26/50 = 52.0%
    v9b top picks: [('lzma2', 25), ('BHTC1', 5), ('brotli', 4),
                   ('BHVT1', 4), ('BHRT1', 2), ('BHJA1', 2),
                   ('BHTL1', 2), ('BHNL1', 1), ('BHTM1', 1), ('bz2', 1)]
```

## Files

- `investigate_ssp5_recommender_v9b.py` — **stable recommender**
- `investigate_ssp5_recommender_v8.py` — predecessor (no locality)
- `investigate_ssp5_recommender_v9.py` — broken (raw locality)
- `investigate_ssp5_recommender_v7.py` — class-balanced k-NN source
- `benchmark/ssp5-recommender-v9b/` — v9b results (rules, loo, corpus)
- `benchmark/ssp5-recommender-v8/` — v8 results + diff vs v9
- `benchmark/ssp5-recommender-v9/` — v9 results (raw locality)
- `benchmark/ssp5-recommender-v7/` — v7 results
- `benchmark/recommender-corpus/` — 50-file real BHA ground truth
- `benchmark/ssp5-42codec/` — 13×42 codec matrix (synthetic ground truth)
- `catalog.ini` — 27 BHA file_codec magics + stdlib

## Provenance

- Commit: `1f4c306 bha-codecs: v9b stable recommender (BHA-dominant locality, real-only top-1 = 42%)`
- Path: `D:\4\bha-codecs\`
- Built: 2026-08-20
