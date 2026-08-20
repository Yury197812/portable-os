"""Adaptive auto-tune - automatically select best compression pipeline per file.

Tests pipeline selection logic:
- Detect file type (CSV, JSON, log, key-value, binary, XML, repetitive)
- For each file type, suggest best pipeline based on prior corpus data
- Run all 6 pipelines if needed
- Pick winner

Pipeline selection rules (from prior 6-file analysis):
- LZMA only:  CSV, JSON, HTML (already structured)
- A+L:        log_high_entropy (entropy detected)
- L+A:        css_repeated, ini_config (key-value)
- L+A+L:      ini_config (nested)
"""
import sys
import json
import csv
import io
import re
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def detect_file_type(data: bytes, filename: str = "") -> str:
    """Heuristic file type detection."""
    sample = data[:8192]
    if not sample:
        return "empty"
    try:
        text = sample.decode("utf-8", errors="replace")
    except Exception:
        return "binary"
    text_lower = text.lower()
    if any(c < " " or c > "~" for c in text):
        return "binary"
    first_line = text.split("\n", 1)[0]
    if filename.lower().endswith(".csv") or ("," in first_line and first_line.count(",") >= 2):
        return "csv"
    if filename.lower().endswith(".json") or text.lstrip().startswith(("{", "[")):
        return "json"
    if filename.lower().endswith(".html") or "<html" in text_lower or "<body" in text_lower:
        return "html"
    if filename.lower().endswith(".xml"):
        return "xml"
    if filename.lower().endswith(".css"):
        return "css"
    if filename.lower().endswith(".ini"):
        return "ini"
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return "log"
    return "unknown"


def suggest_pipelines(file_type: str) -> list:
    """Suggest pipeline order based on file type heuristics."""
    if file_type in ("csv", "json", "html", "xml", "log"):
        return ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"]
    elif file_type in ("ini", "css"):
        return ["lzma_atomize", "atomize_lzma", "lzma_atomize_lzma", "plain_lzma"]
    elif file_type == "binary":
        return ["plain_lzma", "lzma_lzma", "atomize_lzma"]
    return ["plain_lzma", "atomize_lzma"]


def main():
    test_files = [
        "data_csv_100k.csv", "data_json_100k.json",
        "log_high_entropy_tail_512k.log", "html_inline_data_uri_200k.html",
        "css_repeated_150k.css", "ini_config_128k.ini",
        "binary_header_text_payload.log", "random_lcg_256k.bin",
        "log_long_repeated_512k.log", "xml_attrs_300k.xml",
    ]
    print("=== Adaptive Auto-Tune: Pipeline Suggestion by File Type ===")
    print(f"{'File':40s}  {'Type':8s} | {'Suggested Pipelines'}")
    for fname in test_files:
        p = CORPUS / fname
        if not p.exists():
            continue
        data = p.read_bytes()
        ft = detect_file_type(data, fname)
        pipelines = suggest_pipelines(ft)
        print(f"  {fname:38s}  {ft:8s} | {', '.join(pipelines)}")
    out = {
        "rules": {
            "csv, json, html, xml, log": "plain_lzma primary, atomize variants for entropy",
            "ini, css": "lzma_atomize primary (key-value pattern)",
            "binary": "plain_lzma only (atomization doesn't help random data)",
        },
        "pipeline_suggestions": {
            "csv": ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"],
            "json": ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"],
            "html": ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"],
            "xml": ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"],
            "log": ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"],
            "ini": ["lzma_atomize", "atomize_lzma", "lzma_atomize_lzma", "plain_lzma"],
            "css": ["lzma_atomize", "atomize_lzma", "lzma_atomize_lzma", "plain_lzma"],
            "binary": ["plain_lzma", "lzma_lzma", "atomize_lzma"],
        }
    }
    out_path = Path(r"D:\4\bha-codecs\benchmark\adaptive-auto-tune.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8-sig")
    print(f"\nrules saved: {out_path}")


if __name__ == "__main__":
    main()
