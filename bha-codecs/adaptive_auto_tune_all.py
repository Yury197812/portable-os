"""Apply adaptive auto-tune to all 47 corpus files."""
import sys
import json
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
import adaptive_auto_tune_v2 as aat2

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def main():
    files = sorted([p for p in CORPUS.glob("*") if p.is_file() and p.name != "manifest.json"])
    print(f"=== Adaptive Auto-Tune: {len(files)} corpus files ===")
    print(f"{'File':45s}  {'Type':10s} | Suggested Pipelines")
    results = []
    for p in files:
        try:
            data = p.read_bytes()
        except Exception:
            continue
        if len(data) > 5_000_000:
            continue
        ft = aat2.detect_file_type(data, p.name)
        pipelines = aat2.suggest_pipelines(ft)
        results.append({
            "file": p.name,
            "type": ft,
            "pipelines": pipelines,
            "size": len(data),
        })
        print(f"  {p.name:43s}  {ft:10s} | {', '.join(pipelines)}")
    print(f"\nTotal: {len(results)} files analyzed")
    by_type = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r)
    print("\nBy type:")
    for ft, items in sorted(by_type.items()):
        print(f"  {ft:10s}: {len(items)} files")
    out_path = Path(r"D:\4\bha-codecs\benchmark\adaptive-auto-tune-all.json")
    out_path.write_text(json.dumps({
        "n_files": len(results),
        "by_type": {ft: len(items) for ft, items in by_type.items()},
        "results": results,
    }, indent=2), encoding="utf-8-sig")
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
