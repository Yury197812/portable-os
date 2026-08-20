"""Adaptive auto-tune v3 - extended detection (TSV, YAML, JS, markdown).

Extends v2 with:
- .tsv/.tab detection
- .yaml/.yml detection (---)
- .js detection (function keyword)
- .md detection (# headers)
- html detection in json values
"""
import sys
import json
import csv
import io
import re
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def is_text(data):
    if not data:
        return True
    sample = data[:8192]
    text_chars = sum(1 for c in sample if 0x20 <= c <= 0x7e or c in (0x09, 0x0a, 0x0d))
    return text_chars / len(sample) >= 0.95


def detect_file_type(data, filename=""):
    ext = ""
    if filename:
        ext = Path(filename).suffix.lower()
    if ext in [".csv"]:
        return "csv"
    if ext in [".tsv", ".tab"]:
        return "tsv"
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
    if ext in [".yaml", ".yml"]:
        return "yaml"
    if ext in [".js"]:
        return "js"
    if ext in [".md"]:
        return "markdown"
    if ext in [".log"]:
        return "log"
    if ext in [".ts"]:
        return "tsv"
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
        if first_line.count("\t") >= 2:
            return "tsv"
    if text.lstrip().startswith(("{", "[")):
        return "json"
    if "<html" in text.lower() or "<body" in text.lower():
        return "html"
    if re.search(r"^---\s*$", text, re.MULTILINE):
        return "yaml"
    if text.lstrip().startswith("function ") or "=> {" in text or "const " in text:
        return "js"
    if re.search(r"^#\s+\w+", text, re.MULTILINE):
        return "markdown"
    if text.lstrip().startswith("<?xml") or text.lstrip().startswith("<"):
        return "xml"
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return "log"
    return "unknown"


def suggest_pipelines(file_type):
    if file_type in ("csv", "tsv", "json", "html", "xml", "log", "markdown", "yaml"):
        return ["plain_lzma", "atomize_lzma", "lzma_atomize_lzma", "lzma_atomize"]
    elif file_type in ("ini", "css", "js"):
        return ["lzma_atomize", "atomize_lzma", "lzma_atomize_lzma", "plain_lzma"]
    elif file_type == "binary":
        return ["plain_lzma", "lzma_lzma", "atomize_lzma"]
    return ["plain_lzma", "atomize_lzma"]


def main():
    files = sorted([p for p in CORPUS.glob("*") if p.is_file() and p.name != "manifest.json"])
    print(f"=== Adaptive Auto-Tune v3: {len(files)} corpus files ===")
    print(f"{'File':45s}  {'Type':10s} | Suggested Pipelines")
    results = []
    for p in files:
        try:
            data = p.read_bytes()
        except Exception:
            continue
        if len(data) > 5_000_000:
            continue
        ft = detect_file_type(data, p.name)
        pipelines = suggest_pipelines(ft)
        results.append({"file": p.name, "type": ft, "pipelines": pipelines, "size": len(data)})
        print(f"  {p.name:43s}  {ft:10s} | {', '.join(pipelines)}")
    by_type = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r)
    print(f"\nTotal: {len(results)} files analyzed")
    print("\nBy type:")
    for ft, items in sorted(by_type.items()):
        print(f"  {ft:10s}: {len(items)} files")
    out_path = Path(r"D:\4\bha-codecs\benchmark\adaptive-auto-tune-v3.json")
    out_path.write_text(json.dumps({
        "n_files": len(results),
        "by_type": {ft: len(items) for ft, items in by_type.items()},
        "results": results,
    }, indent=2), encoding="utf-8-sig")
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
