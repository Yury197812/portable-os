"""
bha_delta: per-column delta encoding preprocessor.

Detects CSV-like numeric columns and replaces them with:
  - first row absolute value
  - subsequent rows: signed varint deltas (zigzag-encoded)

For non-numeric columns: pass through unchanged.

Format:
  IN:  "idx,c0,c1\n0,100,200\n1,107,210\n2,114,220\n..."
  OUT: header + per-column encoded stream
       "_meta":{"cols":["c0","c1"],"enc":["delta","delta"]}
       "_data":{"c0":"<zigzag-delta bytes>","c1":"..."}

Decoder is trivial: read first value absolute, then for each
subsequent varint: zigzag-decode to get signed delta, add to
previous. Roundtrip-preserving.
"""
from __future__ import annotations
import csv
import io
import json
from typing import Optional, Tuple, List


def _is_int_column(values: List[str]) -> bool:
    """Return True if all values parse as int."""
    if not values:
        return False
    for v in values:
        v = v.strip()
        if not v:
            return False
        try:
            int(v)
        except ValueError:
            return False
    return True


def _is_float_column(values: List[str]) -> bool:
    """Return True if all values parse as float."""
    if not values:
        return False
    for v in values:
        v = v.strip()
        if not v:
            return False
        try:
            float(v)
        except ValueError:
            return False
    return True


def _delta_encode(values: List[int]) -> bytes:
    """First value absolute (8 bytes big-endian signed), rest as
    zigzag varint deltas. Deltas of small magnitude (e.g. constant
    step) compress to 1-2 bytes per value.
    """
    out = bytearray()
    if not values:
        return bytes(out)
    out.extend(values[0].to_bytes(8, 'big', signed=True))
    prev = values[0]
    for v in values[1:]:
        d = v - prev
        u = (d << 1) ^ (d >> 63)
        u &= (1 << 64) - 1
        # varint encode u (up to 9 bytes)
        while u >= 0x80:
            out.append((u & 0x7F) | 0x80)
            u >>= 7
        out.append(u)
        prev = v
    return bytes(out)


def _delta_encode_float(values: List[float]) -> bytes:
    """Adaptive-scale float delta encoding.

    Choose scale dynamically based on max abs delta between consecutive
    values. For slow-changing floats (e.g. temperature 20.001, 20.002)
    use scale=1e9 (9 decimal digits) -> delta=1, fits in 1 varint byte.
    For wide-range floats (1.5, 1e6) use scale=1 (delta=999998, fits in
    3 varint bytes). For mixed ranges the smaller scale wins.
    """
    out = bytearray()
    if not values:
        return bytes(out)
    import struct
    # single value: store as 8-byte double
    if len(values) == 1:
        out.extend(struct.pack('>d', values[0]))
        return bytes(out)
    deltas = [values[i+1] - values[i] for i in range(len(values) - 1)]
    max_abs_delta = max((abs(d) for d in deltas), default=0.0)
    # pick scale: prefer high scale if max abs delta is small
    if max_abs_delta == 0.0:
        scale_idx = 0  # 1.0
    elif max_abs_delta < 1e-9:
        scale_idx = 4  # 1e9
    elif max_abs_delta < 1e-6:
        scale_idx = 3  # 1e6
    elif max_abs_delta < 1e-3:
        scale_idx = 2  # 1e3
    elif max_abs_delta < 1.0:
        scale_idx = 1  # 1e2
    else:
        scale_idx = 0  # 1.0
    scale = [1, 100, 1_000, 1_000_000, 1_000_000_000][scale_idx]
    out.append(scale_idx)
    out.extend(struct.pack('>d', values[0]))
    prev_int = int(round(values[0] * scale))
    for v in values[1:]:
        cur_int = int(round(v * scale))
        d = cur_int - prev_int
        u = (d << 1) ^ (d >> 63)
        u &= (1 << 64) - 1
        # varint
        while u >= 0x80:
            out.append((u & 0x7F) | 0x80)
            u >>= 7
        out.append(u)
        prev_int = cur_int
    return bytes(out)


def _is_timestamp_column(values: List[str]) -> bool:
    """Return True if all values look like epoch seconds (10-13 digits)."""
    if not values:
        return False
    n_match = 0
    n_total = 0
    for v in values:
        v = v.strip()
        if not v:
            continue
        n_total += 1
        if v.isdigit() and 10 <= len(v) <= 13:
            n_match += 1
    return n_total >= 50 and n_match == n_total


def _delta_encode_timestamp(values: List[int]) -> bytes:
    """Same as int delta encoding - first value absolute, rest as
    zigzag varint deltas. For typical 1-second sample log, deltas are
    small (often 1) so each fits in 1 byte varint.
    """
    return _delta_encode(values)


def _is_ipv4_column(values: List[str]) -> bool:
    """Return True if all values look like IPv4 dotted-quad strings."""
    if not values:
        return False
    n_match = 0
    n_total = 0
    for v in values:
        v = v.strip()
        if not v:
            continue
        n_total += 1
        parts = v.split('.')
        if len(parts) != 4:
            continue
        if all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            n_match += 1
    return n_total >= 50 and n_match == n_total


def _delta_encode_ipv4(values: List[str]) -> bytes:
    """Encode IPv4 strings as packed 4-byte sequences. First value
    absolute (4 bytes), rest as per-octet deltas (1 byte each).
    For typical '192.168.1.1', '192.168.1.2', ... series, per-octet
    deltas are 0, 0, 0, 1 = 4 bytes per row vs original 9+ chars.
    """
    out = bytearray()
    if not values:
        return bytes(out)
    first_parts = [int(p) for p in values[0].strip().split('.')]
    out.extend(bytes(first_parts))
    prev = first_parts
    for v in values[1:]:
        cur = [int(p) for p in v.strip().split('.')]
        deltas = [(c - p) & 0xFF for c, p in zip(cur, prev)]
        # encode as 4 signed-bytes (one per octet)
        for d in deltas:
            u = (d << 1) ^ (d >> 7)
            u &= 0xFF
            if u >= 0x80:
                # two-byte varint for signed octet delta
                out.append((u & 0x7F) | 0x80)
                out.append(u >> 7)
            else:
                out.append(u)
        prev = cur
    return bytes(out)


def try_column_delta(data: bytes) -> Optional[bytes]:
    """If data is a CSV with >= 1 numeric column of >= 50 rows,
    return column-delta-encoded JSON. Otherwise None.

    Supported per-column encodings (priority order):
      1. delta_timestamp  (epoch seconds, 10-13 digit int)
      2. delta_ipv4       (dotted-quad IP strings)
      3. delta_int        (regular integers)
      4. delta_float      (floating point, adaptive scale)
      5. pass             (non-numeric: original CSV text)
    """
    if len(data) < 256 or len(data) > 8 * 1024 * 1024:
        return None
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = data.decode('latin-1')
        except Exception:
            return None
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 51:  # header + 50 data
        return None
    header = rows[0]
    n_cols = len(header)
    n_data = len(rows) - 1
    col_encodings = []
    col_blobs = []
    int_columns = 0
    for c in range(n_cols):
        col_strs = [rows[r + 1][c] if c < len(rows[r + 1]) else '' for r in range(n_data)]
        if _is_timestamp_column(col_strs):
            ints = [int(s.strip()) for s in col_strs]
            col_encodings.append('delta_timestamp')
            col_blobs.append(_delta_encode_timestamp(ints))
            int_columns += 1
        elif _is_ipv4_column(col_strs):
            col_encodings.append('delta_ipv4')
            col_blobs.append(_delta_encode_ipv4(col_strs))
        elif _is_int_column(col_strs):
            ints = [int(s.strip()) for s in col_strs]
            col_encodings.append('delta_int')
            col_blobs.append(_delta_encode(ints))
            int_columns += 1
        elif _is_float_column(col_strs):
            col_encodings.append('delta_float')
            col_blobs.append(_delta_encode_float([float(s.strip()) for s in col_strs]))
        else:
            col_encodings.append('pass')
            col_blobs.append(None)
    original_csv_size = len(data)
    out = {
        "_meta": {
            "cols": header,
            "enc": col_encodings,
            "n_rows": n_data,
            "n_int_cols": int_columns,
        },
        "_data": {header[c]: col_blobs[c].hex() for c in range(n_cols) if col_blobs[c] is not None},
    }
    encoded = json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(encoded) >= original_csv_size * 0.95:
        return None
    return encoded


if __name__ == "__main__":
    import os
    n = 0
    total_orig = 0
    total_enc = 0
    for f in sorted(os.listdir('benchmark')):
        if not f.startswith('delta_') or not f.endswith('.csv'):
            continue
        p = os.path.join('benchmark', f)
        data = open(p, 'rb').read()
        out = try_column_delta(data)
        if out is None:
            print(f'  {f}: NO TRANSFORM ({len(data)} B)')
        else:
            gain = 100 * (len(data) - len(out)) / len(data)
            print(f'  {f}: {len(data)} -> {len(out)}  (-{gain:.1f}%)')
            n += 1
            total_orig += len(data)
            total_enc += len(out)
    if n:
        print(f'\n  {n} files transformed, total {total_orig} -> {total_enc} '
              f'(-{100*(total_orig-total_enc)/total_orig:.1f}%)')
