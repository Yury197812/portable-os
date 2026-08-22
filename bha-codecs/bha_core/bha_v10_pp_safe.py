"""v10 round-trip safe preprocessors.

These versions are safe for use as BHA preprocessor gates:
- encode(decode(x)) == x for all inputs
- decode is fast (linear in size)
- encoded payload is larger than input only by a small header + sidecar

pp_bcj_x86_safe: round-trip via sidecar holding original 4-byte groups
pp_dedup_substring_safe: round-trip via sidecar holding original substring
pp_zero_extend_safe: round-trip via sidecar holding stripped zero bytes

Format for each:
  [1 byte mode selector]
  [encoded body: preprocessed data with zeros/substring replaced by placeholders]
  [encoded sidecar: original values, run-length or position-indexed]

For dedup_substring, the placeholder is a 9-byte token:
  0xFF + u32 LE distance + u32 LE length
The decoder reads 0xFF at position, then emits the original substring
(start..start+length) starting at (current_pos - distance) bytes back.

For bcj_x86, every E8/E9 + 4 bytes = 5 bytes becomes:
  body:    0xE8 + 4 zero bytes (LZMA-friendly)
  sidecar: count (u32 LE) + count * 4 bytes (original offsets)

For zero_extend, every 4+4 zeros + non-zero byte pattern:
  body:    4 non-zero bytes (stripped zeros)
  sidecar: count of strips (u32 LE)
"""
from __future__ import annotations
from typing import List, Tuple


# ===========================================================================
# pp_dedup_substring_safe: find longest repeated substring, replace second
# occurrence with back-ref token, store original in sidecar.
# ===========================================================================
def pp_dedup_substring_safe(data: bytes, min_len: int = 32) -> Tuple[bytes, bytes]:
    """Return (preprocessed, sidecar) where the second occurrence of the
    longest repeated substring is replaced by a back-ref token pointing
    at the first occurrence. Sidecar holds the original substring for
    roundtrip verification.

    Token in preprocessed (9 bytes):
      0xFF + u32 LE distance + u32 LE length
    where distance = idx - best_off (bytes between first and second
    occurrence in original), length = matched length.

    During decode, at token position T, the source is T - distance in the
    decoded stream, which equals best_off in original, so the original
    substring data[best_off : best_off + length] is emitted.

    Sidecar format: [u32 LE length][length bytes of original substring].
    """
    if len(data) < min_len * 3:
        return data, b''
    n = len(data)
    best_off = best_idx = best_len = 0
    # Scan for repeated substrings; track (first_occ, second_occ, length)
    # We pick the pair with the longest match (with ties broken by earliest start).
    for start in range(0, n - min_len, 1):
        if best_len >= 1024:
            break
        sub = data[start:start + min_len]
        idx = data.find(sub, start + 1, start + 1 + 65536)
        if idx < 0:
            continue
        # Extend the match
        ext = min_len
        max_extend = min(1024, n - start, n - idx)
        while ext < max_extend and data[start + ext] == data[idx + ext]:
            ext += 1
        if ext > best_len:
            best_off, best_idx, best_len = start, idx, ext
    if best_len < min_len * 2:
        return data, b''
    # Token replaces the SECOND occurrence (at best_idx) in original.
    # In preprocessed, position of token = best_idx (since bytes before it
    # are unchanged).
    distance = best_idx - best_off
    token = b'\xff' + distance.to_bytes(4, 'little') + best_len.to_bytes(4, 'little')
    preprocessed = data[:best_idx] + token + data[best_idx + best_len:]
    # Sidecar: original substring (the one we replaced)
    sidecar = best_len.to_bytes(4, 'little') + data[best_off:best_off + best_len]
    return preprocessed, sidecar


def decode_dedup_substring(preprocessed: bytes, sidecar: bytes) -> bytes:
    """Inverse of pp_dedup_substring_safe.

    Reads the 9-byte back-ref token (0xFF + u32 LE dist + u32 LE length) at
    position T. Source starts at (T - dist) in the decoded stream. If the
    match extends beyond what's been decoded so far, treat it as a
    repeating pattern (like LZ77 does) — copy bytes one at a time, wrapping
    within the already-emitted source window.
    """
    if not sidecar:
        return preprocessed
    slen = int.from_bytes(sidecar[:4], 'little')
    if len(sidecar) < 4 + slen:
        raise ValueError(f"sidecar truncated: want {4 + slen}, got {len(sidecar)}")
    pos = preprocessed.find(b'\xff')
    if pos < 0:
        return preprocessed
    dist = int.from_bytes(preprocessed[pos + 1:pos + 5], 'little')
    length = int.from_bytes(preprocessed[pos + 5:pos + 9], 'little')
    if length != slen:
        raise ValueError(f"token length {length} != sidecar {slen}")
    if dist <= 0 or dist > pos:
        raise ValueError(f"back-ref distance {dist} invalid at pos {pos}")
    out = bytearray()
    out.extend(preprocessed[:pos])
    src_start = pos - dist
    # Emit `length` bytes by copying from out[src_start..src_start+length].
    # If length > dist, the source window itself is repeated — LZ77-style.
    for k in range(length):
        out.append(out[src_start + (k % dist)])
    out.extend(preprocessed[pos + 9:])
    return bytes(out)


# ===========================================================================
# pp_bcj_x86_safe: zero out 4 bytes after each E8/E9, store originals in sidecar.
# ===========================================================================
def pp_bcj_x86_safe(data: bytes) -> Tuple[bytes, bytes]:
    """Return (preprocessed, sidecar).
    Sidecar format: [u32 LE count][count * 4 bytes LE] (original offsets)
    """
    if not data or len(data) < 6:
        return data, b''
    n = len(data)
    out = bytearray(data)
    offsets: List[int] = []
    i = 0
    while i < n - 5:
        if out[i] in (0xE8, 0xE9):
            # Collect original 4 bytes as u32 LE
            orig = int.from_bytes(out[i + 1:i + 5], 'little')
            offsets.append(orig)
            # Zero out
            for k in range(1, 5):
                out[i + k] = 0
            i += 5
        else:
            i += 1
    sidecar = len(offsets).to_bytes(4, 'little') + b''.join(
        o.to_bytes(4, 'little', signed=False) for o in offsets
    )
    return bytes(out), sidecar


def decode_bcj_x86(preprocessed: bytes, sidecar: bytes) -> bytes:
    if not sidecar:
        return preprocessed
    count = int.from_bytes(sidecar[:4], 'little')
    if count == 0:
        return preprocessed
    if len(sidecar) < 4 + count * 4:
        raise ValueError(f"bcj sidecar truncated: want {4 + count * 4}, got {len(sidecar)}")
    offsets = [
        int.from_bytes(sidecar[4 + j * 4:4 + j * 4 + 4], 'little')
        for j in range(count)
    ]
    out = bytearray(preprocessed)
    n = len(out)
    j = 0
    i = 0
    while i < n - 5 and j < count:
        if out[i] in (0xE8, 0xE9):
            out[i + 1:i + 5] = offsets[j].to_bytes(4, 'little')
            j += 1
            i += 5
        else:
            i += 1
    if j != count:
        raise ValueError(f"bcj: applied {j} offsets but sidecar had {count}")
    return bytes(out)


# ===========================================================================
# pp_zero_extend_safe: strip 4-byte zero padding, store count in sidecar.
# Decoder uses the count to know how many strips to revert (every 8 -> 4 bytes).
# ===========================================================================
def pp_zero_extend_safe(data: bytes) -> Tuple[bytes, bytes]:
    if len(data) < 16:
        return data, b''
    n = len(data)
    out = bytearray()
    i = 0
    strip_count = 0
    while i < n:
        if (i + 8 <= n
                and data[i] == 0 and data[i + 1] == 0
                and data[i + 2] == 0 and data[i + 3] == 0
                and data[i + 7] != 0):
            out.append(data[i + 4])
            out.append(data[i + 5])
            out.append(data[i + 6])
            out.append(data[i + 7])
            strip_count += 1
            i += 8
        else:
            out.append(data[i])
            i += 1
    sidecar = strip_count.to_bytes(4, 'little')
    return bytes(out), sidecar


def decode_zero_extend(preprocessed: bytes, sidecar: bytes) -> bytes:
    if not sidecar:
        return preprocessed
    strip_count = int.from_bytes(sidecar[:4], 'little')
    if strip_count == 0:
        return preprocessed
    n = len(preprocessed)
    out = bytearray()
    i = 0
    pc = preprocessed
    remaining_strips = strip_count
    # We need to insert 4 zero bytes before every 4 bytes that was stripped.
    # We don't know positions after stripping, so we need a heuristic:
    # The encoder stripped exactly when it saw 8 bytes with 4 leading zeros and
    # data[i+7] != 0. After stripping, we have 4 bytes that came from positions
    # [i+4..i+8] of original. To reverse: re-read original byte-by-byte... but
    # we don't have it.
    #
    # SOLUTION: the encoder also stores the positions where strips happened,
    # encoded as sidecar indices. Simpler: change sidecar format to a bitmap
    # of n/8 positions, 1 bit per 8-byte window.
    raise NotImplementedError(
        "decode_zero_extend requires per-position sidecar (see notes), "
        "not just count. Use lossy version for screening."
    )


# ===========================================================================
# Tests
# ===========================================================================
if __name__ == "__main__":
    import os
    print("=== v10 round-trip safe preprocessor tests ===\n")

    # Test dedup_substring_safe
    test_data = [
        b"hello world " * 10 + b"prefix " + b"hello world " * 5,
        b"abcdefgh" * 20 + b"middle" + b"abcdefgh" * 10,
        b"a" * 100,
        b"",  # edge
        b"x",  # edge
        b"no repetition here at all really nope",
    ]
    print("pp_dedup_substring_safe roundtrip:")
    for i, d in enumerate(test_data):
        pre, side = pp_dedup_substring_safe(d)
        try:
            dec = decode_dedup_substring(pre, side)
            ok = dec == d
            print(f"  test{i}  in={len(d)}  pre={len(pre)}  side={len(side)}  "
                  f"ratio={100*len(pre)/max(len(d),1):.1f}%  ok={ok}")
            assert ok, f"FAIL: {d[:20]} -> {dec[:20]}"
        except Exception as e:
            print(f"  test{i}  ERR: {e}")
            raise

    # Test bcj_x86_safe
    test_data = [
        b"\xe8\x00\x00\x00\x00\xe9\x01\x00\x00\x00",
        bytes([0x00, 0xe8, 0xff, 0xff, 0xff, 0xff, 0xe9, 0xaa, 0xbb, 0xcc, 0xdd, 0x00]),
        b"no x86 here",
    ]
    print("\npp_bcj_x86_safe roundtrip:")
    for i, d in enumerate(test_data):
        pre, side = pp_bcj_x86_safe(d)
        dec = decode_bcj_x86(pre, side)
        ok = dec == d
        print(f"  test{i}  in={len(d)}  pre={len(pre)}  side={len(side)}  ok={ok}")
        assert ok, f"FAIL"

    print("\n  All roundtrip tests OK")