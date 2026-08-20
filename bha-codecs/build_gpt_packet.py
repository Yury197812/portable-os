"""Build comprehensive BHA packet for GPT exchange.

Includes:
  - All investigation scripts (v1..v7 recommenders + codec matrix + corpus)
  - All benchmark JSON results
  - catalog.ini / catalog.toml (codec catalog)
  - README_INDEX.md auto-generated summary
  - envelope.json + manifest.json + READY.json per bridge protocol

Output: D:\4\OUT_MIMO\bha-codecs-ssp5-recommender__MIMO__20260820T1000Z__v1to7.zip
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(r"D:\4\bha-codecs")
OUT_MIMO = Path(r"D:\4\OUT_MIMO")
TIMESTAMP = "20260820T1200Z"
PACKET_NAME = f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__v1to9b"


# ---------------------------------------------------------------------------
# Catalogue: files to include
# ---------------------------------------------------------------------------
SCRIPTS = [
    # Foundation
    "catalog.ini",
    "catalog.toml",
    "benchmark.py",
    "investigate_all_pipelines.py",
    "investigate_bha_combination.py",
    "investigate_hash_696.py",
    "investigate_random_binary.py",
    "investigate_recursive_atomize.py",
    "investigate_lzma_atomize_logs.py",
    "investigate_ssp5_even_atom.py",
    "investigate_ssp5_real_corpus.py",
    "investigate_ssp5_adaptive.py",
    "investigate_ssp5_adaptive_real.py",
    "investigate_ssp5_42codec.py",
    "investigate_ssp5_multipass.py",
    "investigate_ssp5_vs_bha.py",
    "investigate_recommender_corpus.py",
    # Recommenders v1..v9b
    "investigate_ssp5_recommender.py",
    "investigate_ssp5_recommender_v2.py",
    "investigate_ssp5_recommender_v3.py",
    "investigate_ssp5_recommender_v4.py",
    "investigate_ssp5_recommender_v5.py",
    "investigate_ssp5_recommender_v6.py",
    "investigate_ssp5_recommender_v7.py",
    "investigate_ssp5_recommender_v8.py",
    "investigate_ssp5_recommender_v9.py",
    "investigate_ssp5_recommender_v9b.py",
]

BENCHMARK_DIRS = [
    "benchmark/ssp5-42codec",
    "benchmark/ssp5-adaptive",
    "benchmark/ssp5-adaptive-real",
    "benchmark/ssp5-even-atom",
    "benchmark/ssp5-multipass",
    "benchmark/ssp5-real-corpus",
    "benchmark/ssp5-recommender",
    "benchmark/ssp5-recommender-v2",
    "benchmark/ssp5-recommender-v3",
    "benchmark/ssp5-recommender-v4",
    "benchmark/ssp5-recommender-v5",
    "benchmark/ssp5-recommender-v6",
    "benchmark/ssp5-recommender-v7",
    "benchmark/ssp5-recommender-v8",
    "benchmark/ssp5-recommender-v9",
    "benchmark/ssp5-recommender-v9b",
    "benchmark/ssp5-vs-bha",
    "benchmark/recommender-corpus",
]

# Skip _tmp_sources subdirs — large transient files.
SKIP_SUBSTR = ("_tmp_sources", "__pycache__", ".log")


# ---------------------------------------------------------------------------
# Index.md: human-readable summary of what's inside
# ---------------------------------------------------------------------------
def build_index_md() -> str:
    out = []
    out.append("# BHA SSP5 Recommender v1..v7 — Full Evidence Pack")
    out.append("")
    out.append(f"Built: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    out.append(f"Project root: `{PROJECT_ROOT}`")
    out.append("")
    out.append("## Project context")
    out.append("")
    out.append("Black Hole Archiver (BHA) project. Goal: build a recommender that")
    out.append("chooses the best codec per data type. v1 was a hand-coded decision")
    out.append("tree; v2..v7 are auto-trained k-NN recommenders over a 37-source")
    out.append("synthetic corpus with progressively richer codec registries.")
    out.append("")
    out.append("## Codec registry evolution")
    out.append("")
    out.append("| Version | Codecs in registry | New additions | Status |")
    out.append("|---------|--------------------|---------------|--------|")
    out.append("| v1      | 14 hand-coded KB   | —             | reference |")
    out.append("| v2      | 13 sources × 5 top | k=5 NN        | superseded |")
    out.append("| v3      | 65 weighted points | top-5 augm.   | superseded |")
    out.append("| v4      | 37 sources × 6 stdlib | extended synthetic | superseded |")
    out.append("| v5      | 30 (23 BH env + 6 stdlib) | BHA envelope size model | superseded |")
    out.append("| v6      | 79 (5 pp × 10 env + 6 stdlib) | delta_i64 / transpose / dedup_lines / json_extract | superseded |")
    out.append("| v7      | 74 (8 pp × 5 env + 6 stdlib) | + nul_split / text_dict / collate_keys + class-bal. | superseded |")
    out.append("| v8      | 74 + 50 real-corpus points | train on real bha_magic labels | superseded |")
    out.append("| v9      | 74 + 50 + IDF locality | log(1+N/df) per neighbour | broken (raw locality wrong) |")
    out.append("| **v9b** | **74 + 50 + BHA-dominant locality** | **locality only for BHA codecs** | **STABLE** |")
    out.append("")
    out.append("## LOO + 50-file corpus metrics")
    out.append("")
    out.append("| Ver | LOO top-1 (synth) | LOO top-1 (real) | LOO top-3 (real) | LOO top-5 (real) |")
    out.append("|-----|--------------------|------------------|------------------|------------------|")
    out.append("| v1  | 14/14 overfit     | —                | —                | —                |")
    out.append("| v2  | 5/13 = 38.5%      | —                | —                | —                |")
    out.append("| v3  | 4/13 = 30.8%      | —                | —                | —                |")
    out.append("| v4  | 21/37 = 56.8%     | —                | —                | —                |")
    out.append("| v5  | 19/37 = 51.4%     | —                | —                | —                |")
    out.append("| v6  | 18/37 = 48.6%     | —                | —                | —                |")
    out.append("| v7  | 18/37 = 48.6%     | —                | —                | —                |")
    out.append("| v8  | 1/37 = 2.7%       | 17/50 = 34.0%    | 28/50 = 56.0%    | 29/50 = 58.0%    |")
    out.append("| v9  | 4/37 = 10.8%      | 15/50 = 30.0%    | 25/50 = 50.0%    | 28/50 = 56.0%    |")
    out.append("| **v9b** | **1/37 = 2.7%** | **21/50 = 42.0%** | **26/50 = 52.0%** | **30/50 = 60.0%** |")
    out.append("")
    out.append("## BHA-envelope codecs modelled (size model + preprocessor)")
    out.append("")
    out.append("From `catalog.ini` and `investigate_ssp5_42codec.py:BHA_FILE_MAGICS`:")
    out.append("")
    out.append("```")
    for line in [
        "BHST1 (byte)  - structural string",
        "BHRT1 (int)   - repeating text",
        "BHVT1 (int)   - vertical table",
        "BHSC1 (int)   - sparse column",
        "BHTC1 (int)   - time code",
        "BHTM1 (int)   - timestamp",
        "BHNL1 (byte)  - NUL-separated tokens",
        "BHJA1 (byte)  - JSON-aware",
        "BHQC1 (int)   - quasi-deflate",
        "BHCS1 (byte)  - column store (transpose)",
        "BHMT1 (int)   - matrix",
        "BHSP1 (byte)  - sparse",
        "BHDT1 (int)   - delta table",
        "BHMX1 (int)   - mixed",
        "BHMD1 (int)   - mixed delta",
        "BHCC1 (int)   - cross-column (winner on multi-col telemetry)",
        "BHTL1 (byte)  - text line",
        "BHLZ1 (byte)  - LZ-style",
        "BHDS3 (byte)  - directory solid",
        "BHSD1 (byte)  - directory struct",
        "SDLT1  (byte) - directory line",
        "BHBK1  (byte) - directory block",
        "BHDS1  (byte) - directory stream 1",
        "BHDS2  (byte) - directory stream 2",
    ]:
        out.append(f"  {line}")
    out.append("```")
    out.append("")
    out.append("## Preprocessors (v6 + v7)")
    out.append("")
    out.append("All preprocessors run BEFORE LZMA2, inside BHA envelope. Used by")
    out.append("combo codecs named `<envelope>__<pp>`.")
    out.append("")
    out.append("| Preprocessor | Domain | v6 | v7 | v8 | v9 | Wins on |")
    out.append("|--------------|--------|----|----|----|----|---------|")
    out.append("| identity     | any    | Y  | Y  | Y  | Y  | (control) |")
    out.append("| delta        | any    | Y  | Y  | Y  | Y  | (rare wins) |")
    out.append("| delta_i64    | int streams | Y | Y | Y | Y | arith_prog, syn_even_0/1, real_telem_int |")
    out.append("| transpose    | CSV    | Y  | Y  | Y  | Y  | quoted_csv, telem_log_raw |")
    out.append("| dedup_lines  | repeating text | Y | Y | Y | Y | (control — brotli usually wins) |")
    out.append("| json_extract | JSON   | Y  | Y  | Y  | Y  | json_array |")
    out.append("| nul_split    | NUL-separated | — | Y | Y | Y | BHNL1 analogue |")
    out.append("| text_dict    | text with words | — | Y | Y | Y | (sparse wins) |")
    out.append("| collate_keys | key=value logs | — | Y | Y | Y | ini_config, fixed_width_log |")
    out.append("| bcj_x86      | x86 code | — | N | N | N | dropped — hurts non-x86 |")
    out.append("")
    out.append("**v8**: trains on 50 real corpus files with bha_magic labels (BHCC1/BHNL1/BHJA1/etc.)")
    out.append("in addition to the 37 synthetic sources. Class-balanced k-NN unchanged.")
    out.append("")
    out.append("**v9**: adds IDF locality weight `log(1 + N/df(label))` per query, so codecs")
    out.append("appearing in many neighbours are damped and rare local labels amplified.")
    out.append("")
    out.append("## Key insights (validated empirically)")
    out.append("")
    out.append("1. **Per-chunk adaptive codec ≤ fixed strategy** — oracle selection")
    out.append("   per chunk beats any single codec across all real corpora.")
    out.append("2. **Depth≥2 in compression pipelines = overhead** — LZMA2 already")
    out.append("   collapses entropy; another LZMA2/bz2/brotli on top adds only")
    out.append("   overhead. Single-pass + smart preprocessor wins.")
    out.append("3. **BHCC1 beats per-column atomize on multi-column telemetry** —")
    out.append("   cross-column correlation detection is a real win (3.00% vs 4.07%).")
    out.append("4. **Centered signed delta = width by max|delta|** — not max|val|.")
    out.append("5. **Synthetic ≠ real corpus for benchmarks** — always validate on")
    out.append("   real files. Same algorithm: +5.6× on synth, 0.5× loss on real.")
    out.append("6. **Preprocessor + BHA envelope > stdlib on structured data** —")
    out.append("   v6/v7 recommend `BHCC1__delta_i64` over `brotli` for synthetic")
    out.append("   arithmetic streams (×45 size reduction).")
    out.append("7. **Class-balanced k-NN with `1/sqrt(f/expected)` weights** — v7.")
    out.append("   Amplifies rare classes ~2× without losing signal; top-3 78.4% → 83.8%.")
    out.append("8. **Training on real corpus labels is the biggest single win** — v8.")
    out.append("   Adding 50 real files with bha_magic labels lifts real-only top-1 from")
    out.append("   unknown to 34.0% and BH-family picks from 1/50 to 19/50.")
    out.append("9. **IDF locality weight log(1+N/df(label))** — v9. Amplifies codecs")
    out.append("   rare in local k-NN window. Slight top-1 regression vs v8 (30% vs 34%)")
    out.append("   because BHA's actual picks don't always match locally-rare labels.")
    out.append("10. **BHA-dominant-restricted locality fixes v9** — v9b. Restrict")
    out.append("    locality amplification to BHA file_codec magics (lzma2/BHTC1/BHVT1/")
    out.append("    BHRT1/BHJA1/...). Non-dominant labels (brotli/bz2/zlib) get locality=1.0")
    out.append("    (neutral). Real-only LOO top-1 jumps 17/50 → **21/50 = 42.0%** (vs v8's 34%).")
    out.append("")
    out.append("## File layout in this packet")
    out.append("")
    out.append("```")
    out.append("scripts/")
    out.append("  *.py             — all investigation scripts (v1..v9)")
    out.append("  catalog.ini      — codec catalog (27 BHA envelopes + stdlib)")
    out.append("  catalog.toml     — TOML variant of catalog")
    out.append("benchmark/")
    out.append("  ssp5-42codec/        — 42-codec matrix results")
    out.append("  ssp5-even-atom/      — synthetic even-mask atomize")
    out.append("  ssp5-real-corpus/    — real corpus (dense_numeric_csv, telemetry)")
    out.append("  ssp5-adaptive/       — adaptive atomize synthetic")
    out.append("  ssp5-adaptive-real/  — adaptive atomize real")
    out.append("  ssp5-multipass/      — multipass pass1/pass2/pass3 recipes")
    out.append("  ssp5-vs-bha/         — ssp5 vs BHA on small set")
    out.append("  recommender-corpus/  — 50-file real corpus (BHA wins 45/50)")
    out.append("  ssp5-recommender/    — v1 (14 hand-coded KB)")
    out.append("  ssp5-recommender-v2/ — k=NN baseline")
    out.append("  ssp5-recommender-v3/ — augmented k-NN")
    out.append("  ssp5-recommender-v4/ — extended (37 sources)")
    out.append("  ssp5-recommender-v5/ — + BHA envelope size model")
    out.append("  ssp5-recommender-v6/ — + 5 preprocessors (delta/transpose/...)")
    out.append("  ssp5-recommender-v7/ — + 3 more pp + class-balanced voting")
    out.append("  ssp5-recommender-v8/ — + 50 real-corpus training points")
    out.append("  ssp5-recommender-v9/ — + IDF locality log(1+N/df) [broken]")
    out.append("  ssp5-recommender-v9b/ — + BHA-dominant locality [STABLE]")
    out.append("README_INDEX.md       — this file")
    out.append("```")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Build ZIP
# ---------------------------------------------------------------------------
def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def add_to_zip(zf: zipfile.ZipFile, src: Path, arcname: str):
    zf.write(src, arcname)


def main():
    OUT_MIMO.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_MIMO / f"{PACKET_NAME}.zip"
    manifest_path = OUT_MIMO / f"{PACKET_NAME}.manifest.json"
    envelope_path = OUT_MIMO / f"{PACKET_NAME}.envelope.json"
    ready_path = OUT_MIMO / f"{PACKET_NAME}.READY.json"

    artifacts = []
    file_count = 0
    total_bytes = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. README_INDEX.md
        index_md = build_index_md()
        zf.writestr("README_INDEX.md", index_md)
        # 2. scripts/ — top-level .py files and catalogs
        for name in SCRIPTS:
            p = PROJECT_ROOT / name
            if not p.exists():
                print(f"  skip (missing): {name}")
                continue
            arc = f"scripts/{name}"
            add_to_zip(zf, p, arc)
            sz = p.stat().st_size
            sha = file_sha256(p)
            artifacts.append({"path": arc, "sha256": sha, "size_bytes": sz})
            file_count += 1
            total_bytes += sz
            print(f"  + scripts/{name} ({sz} bytes)")
        # 3. benchmark/<dir>/*.json + *.log (skip _tmp_sources)
        for sub in BENCHMARK_DIRS:
            base = PROJECT_ROOT / sub
            if not base.exists():
                print(f"  skip (missing dir): {sub}")
                continue
            for p in sorted(base.iterdir()):
                if not p.is_file():
                    continue
                if any(s in str(p) for s in SKIP_SUBSTR):
                    continue
                arc = f"benchmark/{sub.split('/',1)[1]}/{p.name}"
                add_to_zip(zf, p, arc)
                sz = p.stat().st_size
                sha = file_sha256(p)
                artifacts.append({"path": arc, "sha256": sha, "size_bytes": sz})
                file_count += 1
                total_bytes += sz
        print(f"  bundled {file_count} files, {total_bytes} bytes uncompressed")

    zip_sha = file_sha256(zip_path)
    zip_size = zip_path.stat().st_size

    # Manifest
    manifest = {
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "project_id": "bha-codecs-ssp5-recommender",
        "message_id": f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__v1to7",
        "parent_message_id": None,
        "iteration_id": f"MIMO-BRIDGE-{TIMESTAMP}",
        "source_agent": "MIMO",
        "target_agent": "GPT",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload_path": f"OUT_MIMO/{PACKET_NAME}.zip",
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "artifacts": artifacts,
        "status": "READY",
        "summary": (
            "Full evidence pack for BHA SSP5 recommender v1..v7. "
            "Includes all investigation scripts (codec matrix, 50-file "
            "corpus eval, preprocessor-aware k-NN), benchmark JSON results "
            "for every iteration, codec catalog, and a human-readable "
            "README_INDEX.md with LOO/corpus metrics per version."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    envelope_path.write_text(json.dumps({
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "envelope_of": manifest["message_id"],
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "status": "READY",
    }, indent=2))
    ready_path.write_text(json.dumps({
        "ready": True,
        "message_id": manifest["message_id"],
        "at": manifest["created_at_utc"],
    }, indent=2))

    print(f"\nDONE.")
    print(f"  zip     -> {zip_path} ({zip_size} bytes)")
    print(f"  manifest-> {manifest_path}")
    print(f"  envelope-> {envelope_path}")
    print(f"  ready   -> {ready_path}")
    print(f"  sha256  -> {zip_sha}")


if __name__ == "__main__":
    main()