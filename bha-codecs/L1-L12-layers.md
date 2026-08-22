# BHA Codec Stack — L1..L12 Layer Decomposition

This document decomposes the Black Hole Archiver (BHA) system into a strict
12-layer hierarchy. Each layer is **independently testable**, has a single
responsibility, and exposes a well-defined contract to the layer above.

The decomposition was extracted from:
- `D:\PROJECT UNIVERSE\01Compression\BHA\black_hole_archiver.py` (5646 lines)
- `D:\4\bha-codecs\catalog.ini` (29 magics + container + runtime)
- `D:\4\bha-codecs\bha.py`, `bha_delta.py`, `bha_parallel.py`,
  `bha_persistent_pool.py`, `bha_v10_pp_safe.py`
- `D:\4\bha-codecs\investigate_ssp5_recommender_v9b.py`

## L1 — Raw Input

**Contract**: `bytes` (any length 0..N)
**Responsibility**: Provide the uncompressed input.
**Files**: `Path.read_bytes()`, network buffers, in-memory strings.
**Lossless**: trivially (identity).
**External mapping**:
- `zstd`'s `compress(data)` argument
- `brotli.compress(data)`
- `lzma.compress(data, format=XZ)`

## L2 — Sniffing / Pattern Detection

**Contract**: `tuple[gate_results: dict[str, bool], features: dict]`
**Responsibility**: Detect structural patterns without modifying input.
**Functions** (from black_hole_archiver.py + our extensions):
- `_quoted_csv_gate`, `_telemetry_csv_gate`, `_sparse_pattern_delimiter`,
  `_record_transpose_gate`, `_vartrans_gate`, `_line_norm_gate`,
  `_json_array_gate`, `_markdown_table_gate`, `_css_struct_gate`,
  `_cross_col_numeric_rows`, `_mixed_formula_gate`, `_sparse_col_gate`,
  `_tabular_col_gate`, `_dense_sparse_delimiter`, `_mixed_delimiter_gate`
- `_is_csv_like`, `_is_int_column`, `_is_float_column`,
  `_is_timestamp_column`, `_is_ipv4_column`, `_is_boolean_column` (bha_delta)
- `pp_bcj_x86_safe`, `pp_dedup_substring_safe` detection (no-op for sniffing)
**External mapping**:
- `brotli`'s static dictionary mode triggers on text
- `zstd`'s `--auto` detects log vs binary
- `lz4`'s `--favor-decSpeed` decides based on heuristics

## L3 — Preprocessor / Domain Transform

**Contract**: `bytes` (lossless output via sidecar)
**Responsibility**: Restructure input to be more compressible downstream.
**Built-in (v10)**:
- `pp_bcj_x86_safe` (BHV2_BCJX) — zero out 4 bytes after E8/E9 in x86
- `pp_dedup_substring_safe` (BHV2_DEDUP) — LZ77 back-ref for repeated substrings
- `pp_zero_extend_safe` (BHV2_ZEXT) — strip 4-byte zero padding
**Built-in (bha_delta)**:
- per-column delta encoding (int/float/timestamp/ip/bool)
- adaptive int encoder (plain delta / delta-of-delta / XOR)
- cross-column delta (delta_int between adjacent columns)
**External mapping**:
- `xz --x86` (BCJ filter)
- `7z`'s BCJ filters (x86/ARM/PowerPC/IA64/ARM64)
- `zstd --long` (long-distance mode)
- `brotli`'s static dictionary (pre-loaded common words)

## L4 — Per-Codec Encoding (Structural)

**Contract**: `bytes` (structural representation; still uncompressed in stream sense)
**Responsibility**: Convert preprocessed bytes into a codec-specific structural
representation.
**Codecs** (21 in catalog.ini):
- **Columnar**: BHTC1 (tabular), BHCC1 (cross-col), BHMX1 (mixed-formula)
- **Row-oriented**: BHRT1 (record-transpose), BHVT1 (vartrans), BHSC1 (sparse-col)
- **Structured text**: BHNL1 (line-norm), BHJA1 (JSON-array), BHQC1 (quoted-csv),
  BHCS1 (CSS-struct), BHMT1 (markdown-table)
- **Pattern**: BHSP1 (sparse-pattern), BHDT1 (dense-sparse), BHMD1 (mixed-delim)
- **Time-series**: BHTM1 (telemetry-csv)
- **Special**: BHTL1 (tail-split), BHST1 (passthrough), BHLZ1 (lzma-fallback)
**External mapping**:
- This layer is **BHA-specific**; no general-purpose codec has it
- Closest analogues: `brotli`'s custom dictionary mode

## L5 — Sidecar / Orchestration

**Contract**: `tuple[body: bytes, sidecar: bytes]`
**Responsibility**: Hold auxiliary information needed by L4 reverse.
**Implementation**: For v10 pp gates, sidecar is appended after LZMA body
inside the envelope (u32 LE length prefix).
**External mapping**:
- `7z` LZMA with filter BCJ stores filter state in sidecar
- `brotli`'s static dictionary is itself a sidecar
- `zstd` dictionaries: pre-shared, but can be per-stream

## L6 — Entropy Coding

**Contract**: `bytes` (compressed bitstream)
**Responsibility**: Replace frequent symbols with shorter codes; statistical
back-end to LZ match-finding.
**Built-in**:
- LZMA2 preset 6 (BHA runtime) — high-compression back-end
- LZMA2 preset 9 EXTREME (BHA safety fallback)
- SSP5 internal entropy (BHA's Solid-State-Pair transform)
**External mapping**:
- `brotli`: range coder + LZ77
- `zstd`: FSE + LZ77
- `lz4`: Huffman + LZ77 (no entropy on literals in fast mode)
- `lzma/xz`: LZMA2 + range coder
- `bzip2`: BWT + MTF + Huffman
- `ppmd`: PPM + range coder
- `snappy`: LZ77 only (no entropy)

## L7 — Magic / Envelope Header

**Contract**: `bytes` (magic + ULEB-encoded lengths + payload)
**Responsibility**: Identify codec; carry structural metadata (uncompressed
size, block boundaries, etc).
**Format**: `[5-byte magic][ULEB original_size][ULEB flags][4-byte LE
compressed_size][L6 entropy body][sidecar if any]`
**Magics**: BHA1 (container), SSP5 (runtime), BHSD1/BHDS1/SDLT1/BHDS3/BHBK1
(directory), BHST1/BHRT1/BHVT1/.../BHLZ1 (file), BHV2_DEDUP/BCJX/ZEXT (v10 pp)
**External mapping**:
- `gzip` header (1F 8B + flags)
- `zstd` header (28 B5 2F FD + frame)
- `xz` header (FD 37 7A 58 5A 00)
- `brotli` (no header — relies on content-type)
- `bzip2` header (BZ)

## L8 — Recommender / Codec Selection

**Contract**: `selected_codec: str, candidates: list[str]`
**Responsibility**: For a given input, predict which codec will produce the
smallest output.
**Algorithm**: k-NN with class-balanced weights and BHA-dominant locality
(see `investigate_ssp5_recommender_v9b.py`)
**Top-1 accuracy**: 42% on 50 real BHA files (stable since v9b)
**External mapping**:
- `brotli` runtime level (11 vs 6) selection
- `zstd` strategy hint (--auto-detect-level)
- Not present in most codecs (caller chooses level)

## L9 — Parallel Orchestrator

**Contract**: `tuple[best_bytes: bytes, meta: dict]`
**Responsibility**: Run multiple gates concurrently, pick smallest output.
**Files**:
- `bha_parallel.bha_parallel_compress` — per-call ProcessPoolExecutor
- `bha_persistent_pool.bha_parallel_compress` — long-lived singleton pool
  (2.14× avg speedup over classic)
**External mapping**:
- Not present in single-codec libraries
- Analogous to: parallel gzip/pigz, parallel bzip2/pbzip2

## L10 — File Format / Archive Container

**Contract**: `bytes` (full archive)
**Responsibility**: Multiple files in one archive; directory structure;
metadata (timestamps, attributes).
**Magics**: BHA1 container, BHSD1/SDLT1/BHDS3/BHBK1 directory formats
**External mapping**:
- `zip` (PK header)
- `tar` (ustar magic at offset 257)
- `7z` (7z BC AF 27 1C)
- `rar` (Rar!)

## L11 — CLI / Integration

**Contract**: subprocess invocations, exit codes, stdout/stderr
**Responsibility**: Provide user-facing interface.
**Files**:
- `bha.py --bench` (CLI benchmark)
- `bha_parallel.py <file>...` (CLI parallel)
- `bench_codecs.py` (multi-codec comparison)
**External mapping**:
- `gzip -c`, `zstd -c`, `brotli --stdout`
- All major codecs ship a CLI

## L12 — Full Pipeline

**Contract**: `tuple[compressed: bytes, metrics: dict]`
**Responsibility**: End-to-end compression with all layers active.
**Flow**: L1 → L2 sniff → L3 preprocess → L4 encode → L5 sidecar →
L6 entropy → L7 envelope → L8 select → L9 parallel → L10 container →
L11 CLI → L12 deliver
**Top result on real corpus**: BHA 2.34% of original (vs brotli-q11 ~3.6%)

---

# Above L12 — Meta-Layers (L13..L18)

L12 is a single compress/decompress call. The meta-layers add intelligence
around L12 to make it safer, observable, adaptive, composable, distributed,
and self-improving.

## L13 — Verification Layer

**Contract**: `tuple[verified: bool, error_msg: str|None]`
**Responsibility**: Confirm that the L1-L12 pipeline produces **bit-exact**
output for known inputs (golden-file testing), and that random inputs survive
1000 round-trips without corruption.

**Key activities**:
- Golden-file corpus: fixed inputs → expected outputs (SHA-256 match)
- Fuzz round-trip: random bytes → encode → decode → assert equal
- Stress test: 1000 iterations of encode/decode on real corpus
- Decoder must reject malformed input (negative tests)

**Files in this project**:
- `bench_codecs.py` does 3-iteration round-trip; `--iter 1000` flags stress mode
- `bha_v10_pp_safe.py` round-trip tests (11 cases)
- `bha_delta.py` round-trip tests (8 cases)
- Future: `bha_verify_corpus.py` — automated SHA-256 match against golden files

**External mapping**:
- `xxhash` / `blake3` checksums in compressed stream footer
- `bzip3` includes internal CRC32 + checksum verification
- `zstd` has `--test` mode that does round-trip validation
- OpenZFS: per-block SHA-256 + Merkle tree verification

**Extracted skill candidate**: `roundtrip-stress-pattern`

## L14 — Metrics & Telemetry

**Contract**: `dict` of time series + histograms
**Responsibility**: Capture per-call and aggregate metrics for monitoring,
debugging, and feeding back into L8 recommender.

**Metrics captured today**:
- per-file: input_size, output_size, ratio, encode_ms, decode_ms
- per-gate: succeeded, error, candidate_size
- per-pool: warm vs cold init time, broken-pool recovery count

**Files in this project**:
- `bha.py --bench --json` outputs structured metrics
- `bha_persistent_pool.bha_parallel_compress` returns `meta` dict
- `bench_codecs.py` outputs JSON to `benchmark/codec-benchmark/results.json`
- `benchmark/persistent-vs-classic/results.json` (from T3)
- `benchmark/v10-pp-gates/results.json` (from T1)

**External mapping**:
- Prometheus / OpenTelemetry
- Codec-specific: `zstd --show-stats`, `brotli --verbose`

**Extracted skill candidate**: `compression-telemetry-pattern`

## L15 — Adaptive Control

**Contract**: `tuple[new_config, rollout_pct]`
**Responsibility**: Use L14 metrics to **modify L8 recommender weights,
L9 worker count, L6 preset selection** automatically.

**Idea**: if L14 shows that brotli_q11 always wins on .html, automatically
update the recommender to short-circuit to brotli without running all gates.

**Implementation status**: **NOT YET IMPLEMENTED** — the recommender v9b
is static (loaded from disk at startup). Need online learning.

**Future work**:
- Per-file metrics → update v9b local IDF weights
- Auto-rollout: A/B test new gates, ramp up % of files
- Auto-tuning: pick worker count from observed throughput

**External mapping**:
- Adaptive bitrate (video codecs)
- Auto-scaling in cloud systems
- Online learning for recommendation systems

**Extracted skill candidate**: `adaptive-codec-control-pattern`

## L16 — Multi-Archive Composition

**Contract**: `tuple[merged_bytes, version_chain]`
**Responsibility**: Combine multiple L12 outputs over time into:
- **Differential archives**: archive_v2 - archive_v1 = small delta
- **Deduplicated archives**: shared blocks across many files
- **Incremental backups**: only changed blocks in archive_v2

**Implementation status**: **NOT YET IMPLEMENTED**.

**Idea**: BHA could add a "dedup" magic prefix that says "this block is
identical to block N of archive X". Then a series of weekly backups
becomes small deltas instead of full re-archives.

**External mapping**:
- ZFS/Btrfs send/receive (block-level deduplication)
- BorgBackup / Restic (chunk-level dedup with rolling hash)
- git packfiles (object deduplication via SHA-1)

**Extracted skill candidate**: `delta-archive-pattern`

## L17 — Distributed / Cloud Tier

**Contract**: `tuple[shard_locations, assembly_order]`
**Responsibility**: Split L12 output across multiple storage nodes,
reassemble on read; replicate for durability.

**Implementation status**: **NOT YET IMPLEMENTED**.

**Idea**: One large BHA archive → split into N Reed-Solomon shards, store
on N+2 cloud buckets. Read: reconstruct from any N shards. Disaster
recovery: lose up to 2 buckets without data loss.

**External mapping**:
- Reed-Solomon / Luby transform codes
- HDFS / Ceph / MinIO erasure coding
- IPFS content addressing
- Backblaze B2 "vaults" with redundancy

**Extracted skill candidate**: `erasure-coded-archive-pattern`

## L18 — Meta-Orchestration (MIMO/AGI level)

**Contract**: `tuple[strategy, expected_outcome]`
**Responsibility**: Multi-objective optimization across all meta-layers:
- Pick codec per file (L8) but also per SHARD of file (within L17)
- Pick entropy level (L6) based on power budget + deadline (L14)
- Pick worker count (L9) based on remaining capacity (L14)
- Decide when to retrain recommender (L15) based on drift (L14)

**Implementation status**: **NOT YET IMPLEMENTED**. This is the layer that
MIMO/AGI systems would coordinate — codec selection becomes a planning
problem rather than a single k-NN lookup.

**Idea**: an LLM-driven agent that has access to L14 metrics and L8
recommender outputs, decides:
- "Brotli would beat LZMA2 by 0.5% but takes 4× longer — skip brotli
  for files >500KB"
- "All CSV files this week had identical column structure — increase
  delta_pp cache hit rate by reusing last column type analysis"
- "Storage cost is $X/month; recompression at level 22 saves $Y/month;
  CPU cost is $Z/month — net win if Y > Z + retrain cost"

**External mapping**:
- Kubernetes scheduler (resource-aware bin-packing)
- TensorRT model selection (latency vs accuracy tradeoffs)
- Adaptive HTTP/2 stream prioritization
- Database query planner with cost model

**Extracted skill candidate**: `meta-compression-orchestration-pattern`

---

## Updated layer dependency graph

```
L1 ──► L2 ──► L3 ──► L4 ──► L5 ──► L6 ──► L7
                  │                       │
                  └──► L8 ──► L9 ──► L10 ─┘
                                  │
                                  ▼
                                 L11
                                  │
                                  ▼
                                 L12 (single call)
                                  │
                  ┌───────────────┼───────────────┐
                  ▼               ▼               ▼
                L13             L14             L16 ──► L17
              verify         metrics             │         │
                  │               │             └────► L18 ─┘
                  └─────► L15 ◄───┘             multi-archive
                      adaptive                   + distributed
```

## Where we are TODAY (2026-08-21)

| Layer | Status | Owner code |
|-------|--------|------------|
| L1-L2  | ✅ Working | black_hole_archiver.py sniffers |
| L3    | ✅ Working + extended this session | bha_delta.py + bha_v10_pp_safe.py |
| L4    | ✅ Working (21 codecs) | catalog.ini |
| L5    | ✅ Working (sidecar pattern) | bha_v10_pp_safe.py |
| L6    | ✅ Working (LZMA2 preset 6/EXTREME) | black_hole_archiver.py |
| L7    | ✅ Working (29 magics) | catalog.ini |
| L8    | ✅ Working v9b (42% top-1) | investigate_ssp5_recommender_v9b.py |
| L9    | ✅ Working + 2.14× speedup this session | bha_persistent_pool.py |
| L10   | ✅ Working | black_hole_archiver.py dir_codecs |
| L11   | ✅ Working | bha.py, bha_parallel.py |
| L12   | ✅ Working | bench_codecs.py |
| L13   | 🟡 Partial — round-trip tests exist but no golden file corpus | bha_v10_pp_safe.py, bha_delta.py |
| L14   | 🟡 Partial — JSON output exists but no aggregation/dashboards | bench_codecs.py |
| L15   | ❌ Not implemented | — |
| L16   | ❌ Not implemented | — |
| L17   | ❌ Not implemented | — |
| L18   | ❌ Not implemented | — |

**Highest leverage next steps** (in order):
1. **L14 → L15 feedback loop**: capture all benchmark results, train
   recommender v11 online; expected top-1 jump from 42% → 55%+
2. **L13 golden file corpus**: lock down regression testing for v9b/v10/v11
3. **L16 differential archive**: critical for backup use case
4. **L15 auto-tuning of L9 worker count**: build on persistent pool
5. **L17 erasure coding**: enable BHA as cold storage backend

## Where to extract skills from

Each layer is a candidate for a skill:
- L2 (sniffing): "binary-data-sniffing-pattern"
- L3 (preprocessor): ✅ extracted as "lossless-preprocessor-pattern"
- L6 (entropy): "entropy-codec-benchmark-pattern"
- L8 (recommender): "k-NN-codec-recommender-pattern"
- L9 (parallel): "persistent-process-pool-pattern"
- L13 (verify): "roundtrip-stress-pattern"
- L14 (metrics): "compression-telemetry-pattern"
- L15 (adaptive): "adaptive-codec-control-pattern"
- L16 (composition): "delta-archive-pattern"
- L17 (distributed): "erasure-coded-archive-pattern"
- L18 (meta): "meta-compression-orchestration-pattern"

## See also

- `D:\4\bha-codecs\README.md` — metrics and history
- `D:\4\bha-codecs\catalog.ini` — full codec enumeration
- `~/.mimocode/skills/lossless-preprocessor-pattern/` — L3 skill
- `~/.mimocode/skills/recursive-skill-extractor/` — meta-skill for L18

---

# Beyond L18 — The Recursive Frontier (L19+)

L18 assumes a single agent plans across all layers. The recursive frontier
asks: **what if the planning agent is itself composed of the same layered
architecture?**

## L19 — Self-Hosting

The BHA codec is used to compress **its own implementation**, including
the L18 orchestrator. If L18 + L17 + L16 + L15 + L14 + L13 + ... < size of
the BHA codebase / 10, the codec has effectively "compiled itself".

This is a benchmark of **algorithmic efficiency**: a better codec needs
fewer bytes to encode itself than a worse codec. (CMix and PAQ score
extremely well on this benchmark because their models are tiny.)

## L21 — Skill Synthesis Loop

Each layer above L12 produces a **skill** when its pattern is repeated.
The skill store (`~/.mimocode/skills/`) becomes:
- L19 — skill metadata (what each layer does)
- L20 — skill orchestration (when to combine)
- **L21 — skill synthesis**: new skills generated automatically by
  finding common patterns across existing skills

## L22 — Meta-Skills for the Recursive Frontier

The L21 synthesised skills then feed back into L18 to improve planning.
The loop closes: **codec → skills → better planning → better codec**.

## L∞ — The Limit

The recursive limit is the smallest possible representation of the codec
itself, given the universe's entropy budget. Approaching this limit is
the same problem as **Kolmogorov complexity**, which is uncomputable.
But we can approach it through:
- Better preprocessors (L3)
- Better entropy coders (L6)
- Better structure detection (L2)
- Better recommender (L8)
- Better verification (L13)
- Better composition (L16)
- Better distribution (L17)
- Better planning (L18)

Every layer above L12 must be **measured** (L14) and **adapted** (L15).
This is the **codec equivalent of AGI**: a system that improves its own
representation across all layers, recursively, until it approaches the
theoretical limit.

## Practical note

L19-L∞ are **research directions**, not implementation tasks. The current
practical work is L13-L18, especially L15 (adaptive control) and L16
(differential archives).

To make progress: instrument everything (L14), feed data to adaptive
controller (L15), validate (L13), then look for higher-level patterns
(L18). Repeat.

---

**Bottom line**: L12 is where today's codecs stop. L18 is where MIMO/AGI
systems begin. The gap between them is filled with verification (L13),
measurement (L14), adaptation (L15), composition (L16), and distribution
(L17). Above L18, the architecture becomes recursive — the codec improves
itself, generating skills (L19-L21) that feed back into better planning
(L18), which generates better codecs, which compress better, which expose
new patterns, which become new skills, ad infinitum until the
Kolmogorov-complexity limit (L∞).