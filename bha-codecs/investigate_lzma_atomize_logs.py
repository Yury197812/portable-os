"""Investigation C: Atomize-then-LZMA on log files.

When LZMA compresses and we re-atomize, is there a benefit? Earlier tests showed
LZMA of binary data does not gain from re-atomize. But for STRUCTURED streams
like log files, this might be different.

Test: take 5 log files, find if LZMA-of-LZMA-of-atomize gives anything
beyond plain LZMA. Specifically, do nested LZMA streams have patterns
that LZMA-atomize pipeline captures?
"""
import sys
import lzma
import io
import re
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def atomize_log(data):
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return data
    ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})")
    ts_list, msg_list = [], []
    for line in text.splitlines():
        m = ts_re.match(line)
        if m:
            ts_list.append(m.group(1))
            msg_list.append(line[len(m.group(1)):].lstrip(" "))
        else:
            ts_list.append("")
            msg_list.append(line)
    out = io.BytesIO()
    out.write(f"FORMAT=LOG\nROWS={len(ts_list)}\n".encode())
    for ts in ts_list:
        out.write(f"T={ts}\n".encode())
    out.write(b"MSG_BEGIN\n")
    for msg in msg_list:
        out.write(f"M={msg}\n".encode())
    return out.getvalue()


def lzma_compress(data, level=9):
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": level}],
                          check=-1)


def main():
    log_files = [
        "log_high_entropy_tail_512k.log",
        "log_long_repeated_512k.log",
        "fixed_aligned_log_256k.log",
        "fixed_width_short_128k.log",
        "pipe_kv_transition_256k.log",
        "pipe_sparse_many_cols_256k.log",
    ]
    print("=== Investigation C: LZMA-then-atomize on log files ===")
    print(f"{'file':40s}  {'orig':>8s} | {'plain':>8s} | {'A_only':>8s} | {'L+A':>8s} | {'L+A+L':>8s} | {'A+L':>8s}")
    for fname in log_files:
        path = CORPUS / fname
        if not path.exists():
            continue
        data = path.read_bytes()
        original = len(data)
        atm = atomize_log(data)
        plain = lzma_compress(data, 9)
        lzma_atm = atomize_log(plain)
        lzma_atm_lzma = lzma_compress(lzma_atm, 9)
        atm_lzma = lzma_compress(atm, 9)
        print(f"  {fname:38s}  {original:>8d} | "
              f"{len(plain):>8d} | "
              f"{len(atm):>8d} | "
              f"{len(lzma_atm):>8d} | "
              f"{len(lzma_atm_lzma):>8d} | "
              f"{len(atm_lzma):>8d}")


if __name__ == "__main__":
    main()
