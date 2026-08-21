# BHA SSP5 Codec Recommender — Unified Metrics v1..v9b

**Recommender that picks the best codec per file for the Black Hole**
**Archiver (BHA). Final stable version: v9b (real-only top-1 = 42.0%).**

Built: 2026-08-20  |  Path: `D:\4\bha-codecs\`  |  License: project-internal

## 1. Summary table v1..v9b

| Ver | Approach | LOO synth top-1 | LOO real top-1 | LOO real top-3 | 50-file real top-1 |
|-----|----------|-----------------|-----------------|-----------------|---------------------|
| **v1** | hand-coded decision tree (14 KB) | 14/14 KB ✓ | — | — | — |
| **v2** | k-NN baseline (13 sources) |  38.5% | — | — | — |
| **v3** | augmented k-NN (13×5=65) |  30.8% | — | — | — |
| **v4** | extended to 37 sources, 6 stdlib |  56.8% | — | — | — |
| **v5** | + 24 BHA-envelope magics (size model) |  51.4% | — | — | — |
| **v6** | + 5 preprocessors (delta/transpose/...) |  48.6% | — | — | — |
| **v7** | + 3 pp + class-balanced k-NN |  48.6% | — | — | — |
| **v8** | v7 training + 50 real corpus points |   2.7% |  34.0% |  56.0% |  34.0% |
| **v9** | v8 + IDF locality log(1+N/df) |  10.8% |  30.0% |  50.0% |  30.0% |
| **v9b** | v8 + locality restricted to BHA-dominant (STABLE) |   2.7% |  42.0% |  52.0% |  42.0% |

## 2. Real-only LOO top-1 (50 real BHA files, leave-one-out)

```
v9b ████████████████████████████████  42.0%   ← STABLE
v8  ███████████████████████████       34.0%
v9  ████████████████████████          30.0%   (raw locality over-amplifies bz2)
v1  ████████████████                  22.0%   (hand-coded KB)
```

## 3. Real-only LOO top-3 (50 files)

```
v8  ████████████████████████████████████  56.0%
v9b ██████████████████████████████████    52.0%
v9  ██████████████████████████████      50.0%
v1  ████████████████                      22.0%
```

## 4. Real-only LOO top-5 (50 files)

```
v9b ██████████████████████████████████████  60.0%   ← STABLE
v8  ███████████████████████████████████      58.0%
v9  █████████████████████████████████        56.0%
```

## 5. Synthetic LOO top-1 over versions (37 synthetic sources)

```
v1  ████████████████████████████████████  100.0% (KB overfit)
v4  ██████████████████                  56.8%
v5  █████████████████                   51.4%
v6  ████████████████                    48.6%
v7  ████████████████                    48.6%
v2  ████████████                        38.5%
v3  ██████████                          30.8%
v9  ███                                  10.8% (synthetic-only LOO not relevant)
v8  █                                    2.7% (synthetic-only LOO not relevant)
v9b █                                    2.7% (synthetic-only LOO not relevant)
```
Note: v8/v9/v9b's synthetic LOO top-1 collapsed because real-corpus
points (50) outweigh synthetic (37), shifting class-balance toward
globally-common lzma2/brotli. This is the correct trade-off for a
real-file deployment; synthetic-only LOO is no longer the relevant
metric for v8+.

## 6. Trajectory of real-only LOO top-1 (v1 → v9b)

```
real-only top-1: 22.0% → ? → ? → ? → ? → ? → ? → 34.0% → 30.0% → 42.0%
                       v1  v2  v3  v4  v5  v6  v7   v8   v9   v9b
                              v2-v7 = synthetic-only LOO (not measured on real corpus)
sparkline: ▁      ▅▃█  (v9 local regression then v9b fix)
```

## 7. Pick distribution shift v8 → v9b (50 real files)

| Codec | v8 | v9b | Δ |
|-------|----|----|---|
| lzma2 | 23 | 25 | +2 |
| BHTC1 | 6 | 5 | -1 |
| brotli | 7 | 4 | -3 |
| BHVT1 | 3 | 4 | +1 |
| BHRT1 | 2 | 2 |  0 |
| BHJA1 | 2 | 2 |  0 |
| BHTL1 | 2 | 2 |  0 |
| BHNL1 | 0 | 1 | +1 |
| BHTM1 | 1 | 1 |  0 |
| BHCC1 | 1 | 1 |  0 |
| BHCC1__transpose | 1 | 1 |  0 |
| BHQC1 | 1 | 0 | -1 |
| bz2 | 1 | 1 |  0 |

Key shifts: lzma2 +2 (BHA-dominant gain), brotli -3 (correctly demoted),
BHVT1 +1 (now correctly chosen for `pipe_kv_transition_256k.log`).

## 8. Key insights (validated across v1..v9b)

1. **Per-chunk adaptive codec ≤ fixed strategy** — oracle by
   post-compression size strictly beats any single codec on real data.
2. **Depth≥2 in compression pipelines = overhead** — LZMA2 already
   collapses entropy; another LZMA2/bz2/brotli on top adds overhead.
3. **BHCC1 cross-column beats per-column atomize on multi-col** —
   cross-column correlation is a real win (3.00% vs 4.07% on telemetry).
4. **Synthetic ≠ real corpus for benchmarks** — always validate on
   real files. Same algorithm: +5.6× synth, 0.5× real loss.
5. **Preprocessor × BHA envelope > stdlib on structured data** —
   `BHCC1__delta_i64` ×45 on arith streams (8.64% → 0.06%).
6. **Class-balanced k-NN with `1/sqrt(f/expected)` weights** — v7.
   sqrt is canonical compromise (Cui et al. 2019, α=0.5).
7. **Real-corpus training points dominate synthetic for k-NN** — v8.
   Adding 50 real files lifts real-only top-1 from N/A to 34.0%.
8. **IDF locality helps ONLY when ground truth is locally rare** — v9.
   Raw locality demotes lzma2 (23/50 ground truth) and amplifies bz2 (0/50).
9. **BHA-dominant-restricted locality fixes v9** — v9b. Restrict
   locality to BHA codecs. Real-only top-1 jumps 17/50 → 21/50 = 42.0%.

## 9. v9b algorithm (3-layer weighted vote)

```python
BHA_DOMINANT = {
    'lzma2', 'BHTC1', 'BHVT1', 'BHRT1', 'BHJA1', 'BHNL1',
    'BHCC1', 'BHTM1', 'BHTL1', 'BHMX1', 'BHQC1', 'BHSP1',
    'BHST1', 'BHDT1', 'BHCS1', 'BHBK1', 'BHDS1', 'BHDS2',
    'BHCC1__delta_i64', 'BHCC1__transpose', 'BHCC1__json_extract',
    'BHCC1__collate_keys', 'raw', ...
}

for each training point (87 total = 37 synth + 50 real):
    d = L1 distance from query to point
    cb = 1 / sqrt(freq(label) / (n/n_classes))   # class-balance (v7)
    locality = log(1 + N/df(label)) if label in BHA_DOMINANT else 1.0
    score[label] += cb / (d + 0.001) * locality

return top-K codecs by accumulated score
```

**Key insight:** Non-dominant labels (brotli, bz2, zlib) get
locality=1.0 (neutral). This stops bz2 from stealing lzma2 votes on
close ties, while BHA codecs (BHTC1, BHVT1, BHRT1, BHJA1) still
benefit from IDF amplification when they appear rarely locally.

## 10. File layout

```
D:\4\bha-codecs\
├── README.md                                  # this file
├── investigate_ssp5_recommender_v9b.py        # STABLE recommender
├── investigate_ssp5_recommender_v8.py        # predecessor
├── investigate_ssp5_recommender_v9.py        # broken (raw locality)
├── investigate_ssp5_recommender_v7.py        # class-balanced k-NN
├── investigate_ssp5_recommender_v1..v6.py    # earlier iterations
├── investigate_ssp5_42codec.py              # 13×42 codec matrix
├── catalog.ini                                # 27 BHA magics + stdlib
├── build_gpt_packet.py                       # ZIP packager
├── collect_metrics.py                         # extract v1..v9b metrics
├── render_charts.py                           # this README
├── compare_v8_v9.py                          # side-by-side JSON
├── analyse_v9_failures.py                    # failure mode analysis
└── benchmark\
    ├── ssp5-42codec/                        # 13×42 matrix results
    ├── recommender-corpus/                   # 50-file real BHA ground truth
    ├── ssp5-recommender/                     # v1 KB
    ├── ssp5-recommender-v2 .. -v9/           # earlier versions
    └── ssp5-recommender-v9b/                 # v9b STABLE + all_versions_metrics
```

## 11. Benchmarks (compression improvements, session 2026-08-21)

### 11.1 BHA vs brotli crossover (100KB - 1MB)

`bench_bha_vs_brotli.py` with 10 fixtures (5 HTML+inline-JSON, 5 JSON-array,
sizes 50/100/200/500/1024 KB).

| Range | Winner | Reason |
|---|---|---|
| HTML < 200KB | BHA | delta_pp / BHA preprocessors win |
| HTML 200-400KB | BHA | same |
| HTML >= 400KB | brotli | static-dictionary advantage |
| JSON < 200KB | brotli | BHA overhead dominates |
| JSON >= 200KB | BHA | BHCC1 etc. win by 4-9% |

### 11.2 delta preprocessor per-pattern gain (16 fixtures, 50-500KB)

| Pattern | Avg gain over raw LZMA2 | Best single result |
|---|---|---|
| arith (linear) | +98.6% | 571KB -> 228 B (0.04%) |
| quadratic | +98.2% |  |
| sparse_random | +50% |  |
| mixed (5-col) | +72.6% |  |
| log (timestamp) | +26% |  |
| ip (dotted-quad) | +92% (sequential IPs) |  |
| status_alt | +98.9% (alternating patterns) | 988KB -> 337 B (0.03%) |
| bool (RLE) | +87% |  |

### 11.3 adaptive-scale float encoding (4 fixtures)

+65% on float-heavy via per-fixture scale selection (1, 100,
1e3, 1e6, 1e9). The 1-byte scale_index header + 8-byte first-value
+ 4-byte delta-varints outperform fixed scale=1e6 by 1.5-2x on
slow-changing (sub-nano) and wide-range (1e12) float series.

### 11.4 ProcessPoolExecutor orchestrator (bha_parallel, 6 fixtures)

Threshold: 500KB. Workers: 8. Coordinator dispatches 14 independent
BHA gates to a worker pool, picks min(encoded_size) across the
worker output, the lzma_fallback_archive, and the caller's baseline.

| File | size | seq (ms) | par (ms) | speedup | par_size | win? |
|---|---:|---:|---:|---:|---:|---|
| delta_arith_500kb | 571KB | 3876 | 881 | **4.40x** | 228 | yes |
| delta_mixed_500kb | 371KB | 2605 | 0 | sp. won | 14722 | yes |
| delta_log_per_sec | 377KB | 4227 | 0 | sp. won | 54735 | yes |
| delta_status_alt | 987KB | 4143 | 4628 | 0.90x | 337 | no |
| bro_html_500k | 1.5MB | 2854 | 7170 | 0.40x | 102 | no |
| bro_html_200k | 1.5MB | 2085 | 4602 | 0.45x | 25412 | no |
| **Total** | | **19791** | **17281** | **1.15x avg** | | 3/6 wins |

Speedup losses on HTML: worker-process startup (~200ms) dominates
the ~100ms encode work. Future direction: persistent worker pool
(ssp_DLL pre-loaded in a daemon) would remove the startup cost.

## 12. Provenance

- Commits: `1f4c306` (v9b), `a324dc4` (README)
- ZIP: `D:\4\OUT_MIMO\bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip`
  - 148 KB, 67 entries (26 scripts + 35 benchmark JSON + 6 envelope manifests)
  - SHA256: `78d82c33995d8a9358cddb90f6aa2ce46bbe79951525edab255e2b4a951e56b1`
