"""Compare:
1. Plain file → atomize → LZMA
2. Plain file → LZMA → atomize → LZMA
3. Plain file → LZMA → LZMA (baseline)
4. Plain file → LZMA (single)

Tests: does atomization + nested LZMA give different results than
plain file + LZMA + atomization?
"""
import sys
import json
import lzma
import csv
import io
import json as _json
from pathlib import Path


def atomize_csv(data):
    """CSV atomize — same as archive-strategy-comparator v2."""
    try:
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows or len(rows) < 2:
            return data
        header = rows[0]
        out = io.BytesIO()
        out.write(f"FORMAT=CSV\nROWS={len(rows)-1}\nCOLS={len(header)}\n".encode())
        for h in header:
            out.write(f"H={h}\n".encode())
        columns = list(zip(*rows[1:]))
        unique_pool = {}
        for col in columns:
            unique = list(dict.fromkeys(col))
            col_name = f"COL{columns.index(col)}"
            out.write(f"{col_name}_UNIQUE={len(unique)}\n".encode())
            for idx, v in enumerate(unique):
                unique_pool[f"{col_name}_{idx}"] = v
        out.write(b"DICT_END\n")
        for k, v in unique_pool.items():
            out.write(f"{k}={v}\n".encode())
        out.write(b"DATA_BEGIN\n")
        n_rows = len(columns[0]) if columns else 0
        for r in range(n_rows):
            row = []
            for col in columns:
                unique = list(dict.fromkeys(col))
                row.append(str(unique.index(col[r])))
            out.write(",".join(row).encode() + b"\n")
        return out.getvalue()
    except Exception:
        return data


def atomize_json(data):
    """JSON atomize."""
    try:
        text = data.decode("utf-8", errors="replace")
        parsed = _json.loads(text)
        if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
            return data
        keys = list(parsed[0].keys())
        out = io.BytesIO()
        out.write(f"FORMAT=JSON\nKEYS={len(keys)}\n".encode())
        for k in keys:
            out.write(f"K={k}\n".encode())
        unique_per_key = {}
        for k in keys:
            unique = list(dict.fromkeys(str(p.get(k, "")) for p in parsed))
            unique_per_key[k] = unique
            out.write(f"U_{k}={len(unique)}\n".encode())
        out.write(b"DICT_END\n")
        for k, lst in unique_per_key.items():
            for idx, v in enumerate(lst):
                out.write(f"#D{k}_{idx}={v}\n".encode())
        out.write(b"DATA_BEGIN\n")
        for obj in parsed:
            row = []
            for k in keys:
                v = str(obj.get(k, ""))
                row.append(str(unique_per_key[k].index(v)))
            out.write(",".join(row).encode() + b"\n")
        return out.getvalue()
    except Exception:
        return data


def atomize_keyvalue(data):
    """Key=value atomize."""
    try:
        text = data.decode("utf-8", errors="replace")
        keys, values = [], []
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                keys.append(k.strip())
                values.append(v.strip())
        if not keys:
            return data
        out = io.BytesIO()
        out.write(f"FORMAT=KV\nKEYS={len(keys)}\n".encode())
        for k in keys:
            out.write(f"K={k}\n".encode())
        for v in values:
            out.write(f"V={v}\n".encode())
        return out.getvalue()
    except Exception:
        return data


def atomize_xml_flat(data):
    """Generic XML-flat atomize."""
    out = io.BytesIO()
    out.write(b"<seq>")
    parts = data.split(b"<")
    for part in parts:
        if not part:
            continue
        out.write(b"<" + part)
    out.write(b"</seq>")
    return out.getvalue()


def auto_atomize(data):
    """Detect format and atomize."""
    sample = data[:5000]
    try:
        text = sample.decode("utf-8", errors="replace")
    except Exception:
        return data
    if "," in text and "\n" in text:
        first = text.split("\n", 1)[0]
        if first.count(",") >= 2:
            return atomize_csv(data)
    if text.lstrip().startswith(("{", "[")):
        try:
            _json.loads(text)
            return atomize_json(data)
        except Exception:
            pass
    if "=" in text and "\n" in text:
        lines = text.split("\n", 5)
        eq_count = sum(1 for l in lines if "=" in l)
        if eq_count >= 2:
            return atomize_keyvalue(data)
    return atomize_xml_flat(data)


def lzma_compress(data, level=9):
    return lzma.compress(data,
                          format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": level}],
                          check=-1)


def test_sequence(filepath, max_size=2_000_000):
    if filepath.stat().st_size > max_size:
        return None
    data = filepath.read_bytes()
    if len(data) == 0:
        return None
    original_size = len(data)
    s_lzma1 = lzma_compress(data, 9)  # LZMA extreme
    s_atm = auto_atomize(data)
    s_atm_lzma = lzma_compress(s_atm, 9)
    s_lzma_atm = auto_atomize(s_lzma1)
    s_lzma_atm_lzma = lzma_compress(s_lzma_atm, 9)
    s_lzma_lzma = lzma_compress(s_lzma1, 9)
    return {
        "file": filepath.name,
        "size": original_size,
        "1_lzma": {"size": len(s_lzma1), "ratio": round(len(s_lzma1) / original_size * 100, 2)},
        "2_atomize": {"size": len(s_atm), "ratio": round(len(s_atm) / original_size * 100, 2)},
        "3_lzma+atomize": {"size": len(s_lzma_atm), "ratio": round(len(s_lzma_atm) / original_size * 100, 2)},
        "4_lzma+atomize+lzma": {"size": len(s_lzma_atm_lzma), "ratio": round(len(s_lzma_atm_lzma) / original_size * 100, 2)},
        "5_atomize+lzma": {"size": len(s_atm_lzma), "ratio": round(len(s_atm_lzma) / original_size * 100, 2)},
        "6_lzma+lzma": {"size": len(s_lzma_lzma), "ratio": round(len(s_lzma_lzma) / original_size * 100, 2)},
    }


def main():
    samples = [
        "data_csv_100k.csv", "data_json_100k.json",
        "log_high_entropy_tail_512k.log", "html_inline_data_uri_200k.html",
        "css_repeated_150k.css", "ini_config_128k.ini",
    ]
    corpus = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
    results = []
    for name in samples:
        p = corpus / name
        if p.exists():
            r = test_sequence(p)
            if r:
                results.append(r)
    print(f"=== Atomize vs LZMA: {len(results)} files ===")
    print(f"{'file':35s}  {'size':>8s} | {'plain':>8s} | {'atomize':>8s} | {'L+A':>8s} | {'L+A+L':>8s} | {'A+L':>8s} | {'L+L':>8s}")
    for r in results:
        print(f"{r['file']:35s}  {r['size']:>8d} | "
              f"{r['1_lzma']['size']:>8d} | "
              f"{r['2_atomize']['size']:>8d} | "
              f"{r['3_lzma+atomize']['size']:>8d} | "
              f"{r['4_lzma+atomize+lzma']['size']:>8d} | "
              f"{r['5_atomize+lzma']['size']:>8d} | "
              f"{r['6_lzma+lzma']['size']:>8d}")
    print()
    print("=== Analysis ===")
    print("Pipeline 1: plain LZMA (baseline)")
    print("Pipeline 2: atomize only (no LZMA)")
    print("Pipeline 3: LZMA then atomize (atomize compressed stream)")
    print("Pipeline 4: LZMA + atomize + LZMA (nested)")
    print("Pipeline 5: atomize then LZMA (compress structured)")
    print("Pipeline 6: LZMA twice (nested LZMA)")
    print()
    print("Key comparisons:")
    for r in results:
        plain = r['1_lzma']['size']
        a_l = r['5_atomize+lzma']['size']
        l_a = r['3_lzma+atomize']['size']
        l_a_l = r['4_lzma+atomize+lzma']['size']
        diff_a_l_vs_plain = plain - a_l
        diff_l_a_vs_a_l = a_l - l_a
        diff_l_a_l_vs_a_l = a_l - l_a_l
        print(f"  {r['file']:30s}: A+L vs plain saved {diff_a_l_vs_plain:+6d}b  |  L+A vs A+L: {diff_l_a_vs_a_l:+6d}b  |  L+A+L vs A+L: {diff_l_a_l_vs_a_l:+6d}b")
    out = Path(r"D:\4\bha-codecs\benchmark\atomize-vs-archive.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8-sig")
    print(f"\nresults saved: {out}")


if __name__ == "__main__":
    main()
