"""Adaptive auto-tune with FIXED detection + multi-pipeline selection.

File-type detection uses:
1. Extension hints (most reliable)
2. Content-based detection via CSV/JSON/header checks
3. Character-class for binary detection
"""
import sys
import json
import csv
import io
import re
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def is_text(data):
    """Check if data is mostly text (>=95% printable ASCII)."""
    if not data:
        return True
    sample = data[:8192]
    text_chars = sum(1 for c in sample if 0x20 <= c <= 0x7e or c in (0x09, 0x0a, 0x0d))
    return text_chars / len(sample) >= 0.95


def detect_file_type(data, filename=""):
    """Heuristic file type detection — uses extension + content."""
    ext = ""
    if filename:
        ext = Path(filename).suffix.lower()
    if ext in [".csv"]:
        return "csv"
    if ext in [".json", ".jsonl"]:
        return "json"
    if ext in [".html", ".htm"]:
        return "html"
    if ext in [".xml"]:
        return "xml"
    if ext in [".css"]:
        return "css"
    if ext in [".ini"]:
        return "ini"
    if ext in [".log"]:
        return "log"
    if not is_text(data):
        return "binary"
    try:
        text = data[:8192].decode("utf-8", errors="replace")
    except Exception:
        return "binary"
    if "," in text and "\n" in text:
        first_line = text.split("\n", 1)[0]
        if first_line.count(",") >= 2:
            return "csv"
    if text.lstrip().startswith(("{", "[")):
        return "json"
    if "<html" in text.lower() or "<body" in text.lower():
        return "html"
    if text.lstrip().startswith("<?xml") or text.lstrip().startswith("<"):
        return "xml"
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return "log"
    return "unknown"


def suggest_pipelines(file_type):
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
    print(f"{'File':40s}  {'Type':10s} | {'Suggested Pipelines'}")
    for fname in test_files:
        p = CORPUS / fname
        if not p.exists():
            continue
        data = p.read_bytes()
        ft = detect_file_type(data, fname)
        pipelines = suggest_pipelines(ft)
        print(f"  {fname:38s}  {ft:10s} | {', '.join(pipelines)}")
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
