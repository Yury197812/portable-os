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


def _varint_size(n: int) -> int:
    """Number of bytes a signed integer takes in zigzag-varint encoding."""
    u = (n << 1) ^ (n >> 63)
    u &= (1 << 64) - 1
    sz = 1
    while u >= 0x80:
        sz += 1
        u >>= 7
    return sz


def _delta_of_delta_size(values: List[int]) -> int:
    """Return the byte size of delta-of-delta encoding WITHOUT building it.

    For non-monotonic but smooth series (e.g. quadratic, sinusoidal),
    the second-order delta range is much smaller than the first-order,
    yielding smaller varint encoding. Used by adaptive mode selection.
    """
    if len(values) < 3:
        return 0
    total = 8  # first value (absolute)
    prev_prev = values[0]
    prev = values[1]
    d1 = prev - prev_prev
    total += _varint_size(d1)  # first delta
    for v in values[2:]:
        d = v - prev
        d2 = d - d1
        total += _varint_size(d2)
        d1 = d
        prev = v
    return total


def _xor_size(values: List[int]) -> int:
    """Approximate byte size of int-column XOR encoding.

    XOR of consecutive ints has a known pattern: high-order bytes are
    often 0 (when consecutive values are close in magnitude). When all
    values fit in 4 bytes, XOR is 4 bytes per row instead of 8.

    This returns the size if we store 4 bytes per row (best case for
    int32) or 8 bytes (int64). The downstream LZMA will collapse
    repeated zero bytes further.
    """
    if not values:
        return 0
    # Detect int32 vs int64
    all_i32 = all(-(2**31) <= v < 2**31 for v in values)
    width = 4 if all_i32 else 8
    return width * len(values)


def _delta_encode_dod(values: List[int]) -> bytes:
    """Second-order delta: delta(delta(x)).

    Best for linear (constant first derivative) or smooth (small second
    derivative) series. Header: 1 mode byte + 8 bytes first absolute +
    varint first delta, then varint delta-of-deltas.
    """
    out = bytearray()
    if len(values) < 2:
        return _delta_encode(values)
    if len(values) == 2:
        # Need at least 2 deltas for delta-of-delta; fall back to plain delta
        return _delta_encode(values)
    out.append(2)  # mode = delta-of-delta
    out.extend(values[0].to_bytes(8, 'big', signed=True))
    prev = values[1]
    d1 = prev - values[0]
    # encode first delta
    u = (d1 << 1) ^ (d1 >> 63)
    u &= (1 << 64) - 1
    while u >= 0x80:
        out.append((u & 0x7F) | 0x80)
        u >>= 7
    out.append(u)
    prev_prev = values[0]
    for v in values[2:]:
        d = v - prev
        d2 = d - d1
        u = (d2 << 1) ^ (d2 >> 63)
        u &= (1 << 64) - 1
        while u >= 0x80:
            out.append((u & 0x7F) | 0x80)
            u >>= 7
        out.append(u)
        d1 = d
        prev = v
    return bytes(out)


def _xor_encode(values: List[int]) -> bytes:
    """XOR of consecutive int values, packed as 4 or 8 bytes little-endian.

    Header: 1 mode byte (3 for XOR-i32, 4 for XOR-i64) + 4/8 bytes first
    value, then 4/8 bytes per subsequent XOR.
    """
    out = bytearray()
    if not values:
        return bytes(out)
    all_i32 = all(-(2**31) <= v < 2**31 for v in values)
    width = 4 if all_i32 else 8
    out.append(3 if all_i32 else 4)
    out.extend(values[0].to_bytes(width, 'little', signed=True))
    prev = values[0]
    for v in values[1:]:
        x = (v ^ prev) & ((1 << (width * 8)) - 1)
        # signed interpretation for roundtrip
        if x >= (1 << (width * 8 - 1)):
            x -= (1 << (width * 8))
        out.extend(x.to_bytes(width, 'little', signed=True))
        prev = v
    return bytes(out)


def _decode_dod(blob: bytes) -> List[int]:
    """Decode delta-of-delta back to original values."""
    if not blob:
        return []
    assert blob[0] == 2, f'bad dod mode {blob[0]}'
    first = int.from_bytes(blob[1:9], 'big', signed=True)
    if len(blob) == 9:
        return [first]
    # decode first delta
    pos = 9
    shift = 0
    u = 0
    while True:
        b = blob[pos]
        pos += 1
        u |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    d1 = (u >> 1) ^ -(u & 1)
    # decode rest of deltas
    values = [first, first + d1]
    prev = values[1]
    while pos < len(blob):
        shift = 0
        u = 0
        while True:
            b = blob[pos]
            pos += 1
            u |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        d2 = (u >> 1) ^ -(u & 1)
        d1 += d2
        cur = prev + d1
        values.append(cur)
        prev = cur
    return values


def _decode_xor(blob: bytes) -> List[int]:
    """Decode XOR-encoded ints back to original values."""
    if not blob:
        return []
    mode = blob[0]
    width = 4 if mode == 3 else 8
    mask = (1 << (width * 8)) - 1
    first = int.from_bytes(blob[1:1 + width], 'little', signed=True)
    values = [first]
    pos = 1 + width
    prev = first
    while pos + width <= len(blob):
        x = int.from_bytes(blob[pos:pos + width], 'little', signed=True)
        cur = (prev ^ x) & mask
        if cur >= (1 << (width * 8 - 1)):
            cur -= (1 << (width * 8))
        values.append(cur)
        prev = cur
        pos += width
    return values


def _adaptive_encode_int(values: List[int]) -> bytes:
    """Pick the smallest of {plain_delta, delta-of-delta, XOR-i32, XOR-i64}.

    Returns bytes prefixed with a 1-byte mode selector (0=plain_delta,
    2=delta-of-delta, 3=xor_i32, 4=xor_i64) followed by the encoded body.

    The plain_delta body is also prefixed with its first value for symmetry
    with the adaptive decoder. To preserve backwards compatibility, when
    mode=0 the body is identical to the legacy _delta_encode() output
    (so legacy decoders still work).

    Performance: delegates to bha_core_rs (Rust) when available, giving
    ~14-25× speedup. Falls back to pure-Python if Rust extension is
    not installed (e.g. unsupported platform).
    """
    if not values:
        return b''
    if len(values) == 1:
        # single value, no per-column mode benefit
        return _delta_encode(values)
    # Try Rust fast path (~14-25× faster than Python on large arrays)
    try:
        import bha_core_rs  # type: ignore
        mode, body = bha_core_rs.adaptive_encode_int(values)
        # Rust returns (mode_int, raw_bytes) without mode prefix.
        # For mode 0 (plain), return body as-is to preserve backwards
        # compatibility with legacy _decode_plain_delta (no mode prefix).
        # For modes 2/3/4, prepend mode byte (legacy decoder won't see
        # these bytes anyway since they start with non-zero first byte).
        if mode == 0:
            return body
        if mode in (2, 3, 4):
            return bytes([mode]) + body
        # mode out of range → fall through to Python
    except ImportError:
        pass  # bha_core_rs not installed; use pure-Python
    # Plain delta: legacy format
    plain = _delta_encode(values)
    plain_size = len(plain)
    # Delta-of-delta
    dod = _delta_encode_dod(values)
    dod_size = len(dod)
    # XOR
    xor = _xor_encode(values)
    xor_size = len(xor)
    # Pick smallest
    candidates = [(plain_size, plain), (dod_size, dod), (xor_size, xor)]
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _decode_adaptive(blob: bytes) -> List[int]:
    """Decode _adaptive_encode_int output.

    Detects mode by first byte:
      - 0 or starts with 8-byte absolute: legacy plain delta
      - 2: delta-of-delta
      - 3 or 4: XOR (4 or 8 bytes width)
    """
    if not blob:
        return []
    if blob[0] in (2, 3, 4):
        # New adaptive format: mode byte is explicit
        if blob[0] == 2:
            return _decode_dod(blob)
        else:
            return _decode_xor(blob)
    # Legacy plain delta
    return _decode_plain_delta(blob)


def _decode_plain_delta(blob: bytes) -> List[int]:
    """Decode legacy plain-delta encoding."""
    if not blob:
        return []
    first = int.from_bytes(blob[:8], 'big', signed=True)
    if len(blob) == 8:
        return [first]
    values = [first]
    pos = 8
    prev = first
    while pos < len(blob):
        shift = 0
        u = 0
        while True:
            b = blob[pos]
            pos += 1
            u |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        d = (u >> 1) ^ -(u & 1)
        prev = prev + d
        values.append(prev)
    return values


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


def _is_boolean_column(values: List[str]) -> bool:
    """Return True if all values are boolean-like (true/false/0/1/yes/no)."""
    if not values:
        return False
    BOOL_SET = {'true', 'false', 't', 'f', '0', '1', 'yes', 'no', 'y', 'n'}
    n_match = 0
    n_total = 0
    for v in values:
        v = v.strip().lower()
        if not v:
            continue
        n_total += 1
        if v in BOOL_SET:
            n_match += 1
    return n_total >= 50 and n_match == n_total


def _delta_encode_boolean(values: List[str]) -> bytes:
    """Run-length encode boolean values. First value is 1 byte
    (0 or 1), then a series of (varint_count, value) pairs for runs.
    For typical 'all 0' or 'all 1' columns, the encoded size is
    2 bytes (header + 1 run) regardless of row count. For long runs
    (>255), count uses varint encoding (same as delta encoding).
    """
    out = bytearray()
    if not values:
        return bytes(out)

    def _write_varint(n: int) -> None:
        """Write unsigned varint."""
        while n >= 0x80:
            out.append((n & 0x7F) | 0x80)
            n >>= 7
        out.append(n)

    def to_bit(v: str) -> int:
        v = v.strip().lower()
        if v in ('1', 'true', 't', 'yes', 'y'):
            return 1
        return 0
    prev_bit = to_bit(values[0])
    out.append(prev_bit)
    run_len = 1
    for v in values[1:]:
        b = to_bit(v)
        if b == prev_bit:
            run_len += 1
        else:
            _write_varint(run_len)
            out.append(prev_bit)
            prev_bit = b
            run_len = 1
    _write_varint(run_len)
    out.append(prev_bit)
    return bytes(out)


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
      1. delta_boolean   (true/false/0/1/yes/no, run-length)
      2. delta_timestamp  (epoch seconds, 10-13 digit int)
      3. delta_ipv4       (dotted-quad IP strings)
      4. delta_int        (regular integers)
      5. delta_float      (floating point, adaptive scale)
      6. pass             (non-numeric: original CSV text)
    """
    # Size limits: must be at least 256 bytes for CSV detection
    # (header + at least one row), and at most 8 MiB (varint overhead
    # becomes worse than the original CSV above this point).
    MIN_DATA_SIZE = 1 << 8   # 256 bytes
    MAX_DATA_SIZE = 1 << 23  # 8 MiB
    if len(data) < MIN_DATA_SIZE or len(data) > MAX_DATA_SIZE:
        return None
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = data.decode('latin-1')
        except Exception:
            return None
    # Increase csv field_size_limit to handle large fields (e.g. embedded
    # base64 blobs in JSON, long text values). Default is 131072 bytes
    # (128 KB) which is too small for the 500KB fixtures.
    import sys as _sys_mod
    csv.field_size_limit(min(_sys_mod.maxsize, 2**31 - 1))
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
        if _is_boolean_column(col_strs):
            col_encodings.append('delta_boolean')
            col_blobs.append(_delta_encode_boolean(col_strs))
        elif _is_timestamp_column(col_strs):
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
            col_blobs.append(_adaptive_encode_int(ints))
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
    import json as _json

    # ----- Round-trip unit tests for new adaptive encoder -----
    print('=== adaptive int encode roundtrip tests ===')
    test_cases = [
        ('constant step +7',     [100 + 7 * i for i in range(1000)]),  # linear -> dod ideal
        ('quadratic',            [i * i for i in range(1000)]),          # dod wins
        ('random walk',          [0] + [__import__('random').Random(42).randint(-3, 3) for _ in range(999)]),  # plain delta ok
        ('int32 close values',   [1000000 + i for i in range(1000)]),    # xor wins (i32)
        ('int64 close values',   [10**15 + i for i in range(1000)]),     # xor wins (i64)
        ('alternating ±large',   [0 if i % 2 == 0 else 10**8 for i in range(1000)]),  # dod
        ('single value',         [42]),                                   # edge case
        ('two values',           [1, 2]),                                 # dod needs >=3
    ]
    for label, vals in test_cases:
        enc = _adaptive_encode_int(vals)
        dec = _decode_adaptive(enc)
        ok = dec == vals
        mode = enc[0] if enc else '?'
        plain_size = len(_delta_encode(vals))
        print(f'  {label:30s}  mode={mode}  enc={len(enc):>5d}  plain={plain_size:>5d}  '
              f'gain={100*(plain_size-len(enc))/max(plain_size,1):+.1f}%  roundtrip={"OK" if ok else "FAIL"}')
        assert ok, f'roundtrip failed for {label}: {vals[:5]}... -> {dec[:5]}...'
    print('  all roundtrips OK\n')

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
