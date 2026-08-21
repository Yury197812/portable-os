"""BHA vs Brotli — large files (≥100 KB), Brotli-friendly domain.

Finds real JSON files >100KB, plus generates one big HTML/JS bundle.
Compares BHA vs brotli q6, q11 with both ratio AND pack time.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from pathlib import Path

import brotli


BHA_CLI = r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py"
OUT_JSON = Path(r"D:\4\bha-codecs\benchmark\bha_vs_brotli_large.json")


def find_big_json() -> list[str]:
    out: list[str] = []
    base = Path(r"D:\4\03_literature_data")
    for p in base.glob("*.json"):
        sz = p.stat().st_size
        if sz >= 100_000:
            out.append(str(p))
            if len(out) >= 6:
                break
    return out


def gen_html_bundle(n_kb: int) -> Path:
    """Generate a real-shaped HTML+inline JSON bundle (Brotli-favored)."""
    rnd = random.Random(42)
    parts: list[str] = []
    parts.append("<!DOCTYPE html>\n<html lang=\"ru\">\n<head>")
    parts.append("<meta charset=\"utf-8\">")
    parts.append("<title>Brotli-specific content sample</title>")
    parts.append("<style>")
    css_rules = []
    for i in range(80):
        cls = f"cls-{i:03d}"
        css_rules.append(
            f".{cls} {{ display: {'block' if i%2 else 'inline-block'}; "
            f"padding: {i}px; margin: {i//2}px; color: hsl({i*4}, 60%, 50%); }}"
        )
    parts.append("\n".join(css_rules))
    parts.append("</style></head><body><div class=\"container\">")
    # Repeated card blocks
    templates = [
        ("Пользователь", "user_id"),
        ("Запрос", "request_id"),
        ("Ответ", "response_id"),
        ("Время", "timestamp"),
        ("Статус", "status_code"),
    ]
    rows = []
    for i in range(2000):
        cells = []
        for label, key in templates:
            cells.append(
                f"<td><span class=\"lbl\">{label}</span>"
                f"<span class=\"val\" data-{key}=\"{i:06d}\">{i:06d}</span></td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    parts.append("<table class=\"grid\"><tbody>" + "".join(rows) + "</tbody></table>")

    parts.append("<script>")
    # Realistic JSON-like JS object
    obj = {"users": [], "items": [], "metadata": {"version": "1.0.0", "ts": 1700000000}}
    for i in range(2000):
        obj["users"].append({
            "id": i, "name": f"user_{i:05d}",
            "email": f"user{i}@example.com",
            "role": ["admin", "editor", "viewer"][i % 3],
            "active": i % 2 == 0,
        })
        obj["items"].append({
            "sku": f"SKU-{i:07d}",
            "title": f"Товар номер {i}",
            "price": round(rnd.uniform(10, 9999), 2),
            "tags": [f"tag_{i%50}", f"cat_{i%20}"],
        })
    parts.append("const DATA = " + json.dumps(obj, ensure_ascii=False) + ";")
    parts.append("function render(){return DATA.users.map(u => u.id).join(',');}")
    parts.append("render();")
    parts.append("</script>")
    parts.append("</div></body></html>")
    text = "\n".join(parts)
    out = Path(r"D:\4\bha-codecs\benchmark\bro_specific_html_500k.html")
    # Pad to roughly n_kb by repeating table rows
    target = n_kb * 1024
    while len(text.encode("utf-8")) < target:
        # add a copy of the rows
        parts.insert(-2, "\n".join(rows[:500]))
        text = "\n".join(parts)
    data = text.encode("utf-8")
    out.write_bytes(data)
    return out


def brotli_bench(data: bytes, q: int) -> dict:
    t = time.perf_counter()
    c = brotli.compress(data, quality=q)
    pack_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    r = brotli.decompress(c)
    dec_ms = (time.perf_counter() - t) * 1000.0
    assert r == data
    return {
        "size": len(c),
        "ratio_pct": round(100.0 * len(c) / len(data), 4),
        "pack_ms": round(pack_ms, 2),
        "decode_ms": round(dec_ms, 2),
    }


def bha_bench(paths: list[str]) -> dict:
    cmd = [sys.executable, BHA_CLI, "benchmark", "--json", *paths]
    t = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    elapsed = (time.perf_counter() - t) * 1000.0
    if proc.returncode != 0:
        return {"error": proc.stderr}
    j = json.loads(proc.stdout)
    return {
        "by_path": {r["path"]: r for r in j["rows"]},
        "total_elapsed_ms": round(elapsed, 2),
    }


def main() -> int:
    inputs: list[str] = find_big_json()
    print(f"Found {len(inputs)} big real JSON files")
    for p in inputs:
        print(f"  {Path(p).name}: {Path(p).stat().st_size} bytes")

    # Add a generated large HTML (Brotli-favored)
    html = gen_html_bundle(500)
    print(f"Generated {html.name}: {html.stat().st_size} bytes")
    inputs.append(str(html))

    rows: list[dict] = []
    print(f"\n{'file':50s} {'in':>10s}  {'BHA':>9s} {'q6':>9s} {'q11':>9s}  {'BHA%':>6s} {'q6%':>6s} {'q11%':>6s}  BHA_ms q6_ms q11_ms  verdict")
    for p in inputs:
        data = Path(p).read_bytes()
        b6 = brotli_bench(data, 6)
        b11 = brotli_bench(data, 11)
        brotli_results = {"q6": b6, "q11": b11}

    # BHA in batch
    print(f"\n--- BHA benchmark on {len(inputs)} files ---")
    bha_raw = bha_bench(inputs)

    for p in inputs:
        data = Path(p).read_bytes()
        b6 = brotli_bench(data, 6)
        b11 = brotli_bench(data, 11)
        bha_row = bha_raw["by_path"].get(p, {})
        bha_size = bha_row.get("archive_bytes", -1)
        if bha_size < 0:
            verdict = "n/a"
        elif bha_size < b11["size"]:
            verdict = "BHA<q11"
        elif bha_size < b6["size"]:
            verdict = "BHA<q6"
        else:
            verdict = "brotli"
        rows.append({
            "file": Path(p).name,
            "size_in": len(data),
            "bha_size": bha_size,
            "bha_ratio_pct": bha_row.get("ratio_pct"),
            "bha_pack_ms": bha_row.get("pack_ms"),
            "brotli_q6_size": b6["size"],
            "brotli_q6_ratio_pct": b6["ratio_pct"],
            "brotli_q6_pack_ms": b6["pack_ms"],
            "brotli_q6_decode_ms": b6["decode_ms"],
            "brotli_q11_size": b11["size"],
            "brotli_q11_ratio_pct": b11["ratio_pct"],
            "brotli_q11_pack_ms": b11["pack_ms"],
            "brotli_q11_decode_ms": b11["decode_ms"],
            "verdict": verdict,
            "delta_bha_minus_q11_pct": round(100.0 * (bha_size - b11["size"]) / b11["size"], 2) if bha_size > 0 else None,
        })
        print(
            f"{Path(p).name:50s} {len(data):>10d}  "
            f"{bha_size:>9d} {b6['size']:>9d} {b11['size']:>9d}  "
            f"{bha_row.get('ratio_pct', 0):>6.2f} {b6['ratio_pct']:>6.2f} {b11['ratio_pct']:>6.2f}  "
            f"{bha_row.get('pack_ms', 0):>6.0f} {b6['pack_ms']:>5.0f} {b11['pack_ms']:>6.0f}  {verdict}"
        )

    valid = [r for r in rows if r["bha_size"] > 0]
    n_bha_wins = sum(1 for r in valid if r["bha_size"] < r["brotli_q11_size"])
    n_bha_beats_q6 = sum(1 for r in valid if r["bha_size"] < r["brotli_q6_size"])
    bha_total = sum(r["bha_size"] for r in valid)
    q6_total = sum(r["brotli_q6_size"] for r in valid)
    q11_total = sum(r["brotli_q11_size"] for r in valid)
    in_total = sum(r["size_in"] for r in valid)

    summary = {
        "files_compared": len(valid),
        "bha_total_bytes": bha_total,
        "brotli_q6_total_bytes": q6_total,
        "brotli_q11_total_bytes": q11_total,
        "input_total_bytes": in_total,
        "bha_overall_ratio_pct": round(100.0 * bha_total / in_total, 4),
        "brotli_q6_overall_ratio_pct": round(100.0 * q6_total / in_total, 4),
        "brotli_q11_overall_ratio_pct": round(100.0 * q11_total / in_total, 4),
        "bha_wins_vs_q11": n_bha_wins,
        "bha_wins_vs_q6": n_bha_beats_q6,
        "bha_total_size_minus_q11_pct": round(100.0 * (bha_total - q11_total) / q11_total, 2),
    }
    print("\n=== SUMMARY (large files, Brotli-friendly content) ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = {
        "summary": summary,
        "rows": rows,
        "inputs": inputs,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
