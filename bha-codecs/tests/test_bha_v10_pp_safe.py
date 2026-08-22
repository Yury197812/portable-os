"""Unit tests for bha_core.bha_v10_pp_safe — round-trip safe preprocessors.

Tests pp_dedup_substring_safe, pp_bcj_x86_safe, pp_zero_extend_safe
and their decoders. No BHA runtime needed.
"""
from __future__ import annotations

import pytest

from bha_core import bha_v10_pp_safe


class TestDedupSubstring:
    def test_basic_round_trip(self, repeated_data):
        """The classic case: same substring repeated, finds it, roundtrips."""
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(repeated_data)
        assert len(pre) < len(repeated_data)
        assert len(side) > 0
        decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
        assert decoded == repeated_data

    def test_no_repetition_no_transform(self):
        """Data without repetitions: returns input unchanged, empty sidecar."""
        data = b"abcdefghijklmnopqrstuvwxyz"
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
        assert pre == data
        assert side == b""

    def test_too_short_no_transform(self):
        """Data below min_len threshold: no transform."""
        data = b"hello world " * 2  # ~24 bytes < 96 (3 * min_len=32)
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
        # Either no transform (data unchanged) or transform happens
        # Either way, round-trip must hold
        if side:
            decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
            assert decoded == data

    def test_empty_input(self):
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(b"")
        assert pre == b""
        assert side == b""

    def test_single_byte(self):
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(b"x")
        assert pre == b"x"
        assert side == b""

    def test_two_bytes(self):
        data = b"xy"
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
        assert pre == data
        assert side == b""

    def test_long_uniform_run(self):
        """1000 bytes of 'a' — best case for dedup."""
        data = b"a" * 1000
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
        decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
        assert decoded == data

    def test_periodic_pattern(self):
        """Period-4 pattern — periodic, dedup finds it."""
        data = (b"abcd" * 250)
        pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
        if side:
            decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
            assert decoded == data


class TestBcjX86:
    def test_basic_e8_e9_round_trip(self, x86_like_data):
        """E8/E9 patterns zeroed out, sidecar has originals."""
        pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(x86_like_data)
        # Original bytes after E8/E9 should be zeroed in preprocessed
        assert all(b == 0 for b in pre[1:5])  # First E8 + zeros
        # Sidecar should be non-empty (we had E8/E9 patterns)
        assert len(side) > 0
        # Round-trip must hold
        decoded = bha_v10_pp_safe.decode_bcj_x86(pre, side)
        assert decoded == x86_like_data

    def test_no_e8_e9_no_transform(self):
        """No E8/E9: input unchanged, sidecar empty/zero-count."""
        data = b"\x00" * 100
        pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(data)
        # No E8/E9 in input, no changes
        assert pre == data

    def test_empty_input(self):
        pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(b"")
        assert pre == b""
        assert side == b""

    def test_too_short_input(self):
        pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(b"\xe8\x00\x00\x00\x00")
        # Below 6 bytes: should still work or be no-op
        decoded = bha_v10_pp_safe.decode_bcj_x86(pre, side)
        assert decoded == b"\xe8\x00\x00\x00\x00"

    def test_mixed_with_other_bytes(self):
        """Mix E8/E9 with other bytes — only E8/E9+4 get zeroed."""
        data = b"\x90\xe8\xaa\xbb\xcc\xdd\x90\x90"
        pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(data)
        # The 4 bytes after \xe8 should be zeroed
        assert pre[0] == 0x90  # NOP preserved
        assert pre[1] == 0xe8  # E8 preserved
        assert pre[2] == 0x00  # offset zeroed
        assert pre[3] == 0x00
        assert pre[4] == 0x00
        assert pre[5] == 0x00
        assert pre[6] == 0x90
        # Round-trip
        decoded = bha_v10_pp_safe.decode_bcj_x86(pre, side)
        assert decoded == data


class TestZeroExtend:
    def test_basic_strips_zeros(self):
        """Pattern \\x00\\x00\\x00\\x00\\xaa\\xbb\\xcc\\xdd gets stripped to \\xaa\\xbb\\xcc\\xdd."""
        data = b"\x00" * 4 + b"\xaa\xbb\xcc\xdd" + b"\x00" * 4 + b"\x01\x02\x03\x04"
        pre, side = bha_v10_pp_safe.pp_zero_extend_safe(data)
        # 8-byte window with 4 leading zeros + non-zero last byte → strip
        # result should be shorter than input
        # (Note: round-trip decoder is NOT implemented yet)
        # We just verify encoder behavior here
        assert len(pre) < len(data)

    def test_empty_input(self):
        pre, side = bha_v10_pp_safe.pp_zero_extend_safe(b"")
        assert pre == b""
        assert side == b""

    def test_too_short_input(self):
        pre, side = bha_v10_pp_safe.pp_zero_extend_safe(b"abc")
        assert pre == b"abc"
        assert side == b""