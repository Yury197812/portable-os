# BHA vs Brotli — Brotli-specific content benchmark

**Date:** 2026-08-21  
**Comparator:** our BHA archiver (`D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py`)  
**Baseline:** system `brotli` (Python bindings, quality 6/9/11)  
**Domain:** "Brotli-specific content" = text/web corpora where Brotli is canonically top-1: HTML+inline JSON, structured JSON, Markdown.

## Test corpus

| kind | file | in bytes |
|---|---|---|
| html+inline-json | `bro_html+json-50k.html` | 3 435 |
| html+inline-json | `bro_html+json-80k.html` | 5 557 |
| json | `bro_json-50k.json` | 9 692 |
| json | `bro_json-80k.json` | 15 487 |
| markdown | `bro_markdown-50k.md` | 95 851 |
| markdown | `bro_markdown-80k.md` | 153 857 |
| html+inline-json | `bro_specific_html_200k.html` (1.5 MB) | 1 536 812 |

Source: `D:\4\bha-codecs\bench_bha_vs_brotli_small.py`,
`D:\4\bha-codecs\bench_bha_vs_brotli_final.py`.
Raw: `D:\4\bha-codecs\benchmark\bha_vs_brotli_small.json`,
`D:\4\bha-codecs\benchmark\bha_vs_brotli.json`.

## Headline result (small files, 3-154 KB)

| codec | total bytes | overall ratio | total pack ms | vs brotli q11 (size) |
|---|---:|---:|---:|---|
| **brotli q11** | 3 346 | **1.18%** | 147.7 | — (winner) |
| brotli q9 | 3 695 | 1.30% | n/a | +10.4% |
| brotli q6 | 3 720 | 1.31% | 15.3 | +11.2% |
| **BHA** | **4 277** | **1.51%** | **9 191.2** | **+27.8%** |

**Verdict on small files:** Brotli beats BHA on every file except
`bro_json-80k.json` (where BHA is 1% smaller than q6).
Brotli q11 is 28% smaller than BHA on average, and **~600× faster** to pack.

## Large file (1.5 MB HTML+inline-JSON)

| codec | bytes | ratio | pack time |
|---|---:|---:|---:|
| **BHA** | 23 080 | **1.50%** | 32.85 s |
| brotli q9 | 34 442 | 2.24% | 64 ms |
| brotli q11 | 36 877 | 2.40% | 4.53 s |
| brotli q6 | 40 811 | 2.66% | 30 ms |

**Verdict on the 1.5 MB HTML:** BHA wins on size by **37% over q11** and **44% over q6**,
but loses on time by **~7×** vs brotli q11 and **~1000×** vs brotli q6.

## Crossover

There is a **size crossover** between BHA and Brotli somewhere in
the 100 KB – 1.5 MB range on highly repetitive content. On files
<100 KB the BHA envelope overhead (~370-700 bytes per file) plus
the structured-transform pipeline cancels out the entropy-coding
advantage. On 1.5 MB+ BHA's per-chunk structured codecs
(`BHTC1`, `BHCC1`, etc.) plus LZMA fallback give it the edge on
patterns Brotli's dictionary is not tuned for.

## Per-file table (small)

| file | in | BHA | q6 | q9 | q11 | verdict |
|---|---:|---:|---:|---:|---:|---|
| bro_html+json-50k.html | 3 435 | 615 | 472 | 470 | 424 | brotli |
| bro_html+json-80k.html | 5 557 | 705 | 579 | 591 | 510 | brotli |
| bro_json-50k.json | 9 692 | 793 | 773 | 770 | 673 | brotli |
| bro_json-80k.json | 15 487 | 1 005 | 1 038 | 1 006 | 900 | BHA<q6 |
| bro_markdown-50k.md | 95 851 | 559 | 405 | 406 | 380 | brotli |
| bro_markdown-80k.md | 153 857 | 600 | 453 | 452 | 459 | brotli |

## BHA time / scalability caveat

On files **>~1 MB of HTML/web content BHA's `_compress_best` enters a
long retry loop over the structural codecs** and the test timed out
at 600 s. That's a known property of the current BHA architecture
(see `black_hole_archiver.py:2817` `_compress_best` retry budget) —
it works fine on tabular/structured numeric data, but on heavy
HTML+JSON it tries every transform path before falling back. The
single 1.5 MB HTML run that did finish took 32.85 s; smaller files
(≤80 KB) finish in 0.3-4.7 s.

## Recommendation

- For **files <100 KB** in the Brotli domain: keep brotli, BHA adds size + time.
- For **files >1 MB of repetitive HTML+JSON**: BHA wins on size by ~40%, brotli wins on time by 7-1000×. Choose by use case.
- For **tabular/numeric/log** (BHA's existing ground): stick with BHA — brotli can't compete there at all (`ssp5-vs-bha` JSON shows brotli typically 4-5× worse).
- The real win is the **BHA recommender (v9b)**: it now picks brotli
  for small web-content and BHA structural codecs for everything
  else, getting 42% LOO top-1 on the 50-file real corpus.

## Reproduction

```bash
python D:\4\bha-codecs\bench_bha_vs_brotli_small.py
python D:\4\bha-codecs\bench_bha_vs_brotli_final.py
```
