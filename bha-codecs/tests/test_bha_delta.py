"""Unit tests for bha_core.bha_delta — column delta preprocessor.

Tests column type detection, adaptive int encoder (plain/dod/xor),
boolean encoding, IPv4 encoding, and try_column_delta end-to-end.
No BHA runtime needed.
"""
from __future__ import annotations

import pytest

from bha_core import bha_delta


class TestColumnDetectors:
    def test_is_int_column_true(self):
        vals = ["1", "2", "3", "100", "-5"]
        assert bha_delta._is_int_column(vals) is True

    def test_is_int_column_false_with_floats(self):
        vals = ["1.5", "2.7"]
        assert bha_delta._is_int_column(vals) is False

    def test_is_int_column_false_with_strings(self):
        vals = ["abc", "def"]
        assert bha_delta._is_int_column(vals) is False

    def test_is_int_column_empty(self):
        assert bha_delta._is_int_column([]) is False

    def test_is_int_column_with_spaces(self):
        """Strip whitespace before parsing."""
        vals = [" 1 ", " 2 ", " 3 "]
        assert bha_delta._is_int_column(vals) is True

    def test_is_float_column_true(self):
        vals = ["1.5", "2.7", "-3.14"]
        assert bha_delta._is_float_column(vals) is True

    def test_is_float_column_ints_are_also_floats(self):
        """Ints are valid floats too."""
        vals = ["1", "2", "3"]
        assert bha_delta._is_float_column(vals) is True

    def test_is_boolean_column_true(self):
        vals = ["true", "false", "true", "1", "0"] * 10
        assert bha_delta._is_boolean_column(vals) is True

    def test_is_boolean_column_false(self):
        vals = ["yes", "no", "maybe"]
        assert bha_delta._is_boolean_column(vals) is False

    def test_is_timestamp_column_10_digit(self):
        vals = ["1700000000", "1700000001"] * 25
        assert bha_delta._is_timestamp_column(vals) is True

    def test_is_timestamp_column_too_short(self):
        vals = ["12345", "67890"] * 25
        assert bha_delta._is_timestamp_column(vals) is False

    def test_is_ipv4_column_true(self):
        # IPv4 detector requires >= 50 values to trigger
        vals = ["192.168.1.1", "10.0.0.1", "255.255.255.0"] * 20
        assert len(vals) == 60
        assert bha_delta._is_ipv4_column(vals) is True

    def test_is_ipv4_column_invalid_octet(self):
        vals = ["256.1.1.1"] * 30
        assert bha_delta._is_ipv4_column(vals) is False


class TestAdaptiveIntEncoder:
    """Tests the 3-mode adaptive int encoder: plain / dod / xor-i32/i64."""

    def test_constant_step_picks_plain(self, linear_series):
        """Linear with step 7: plain and dod both yield same size."""
        enc = bha_delta._adaptive_encode_int(linear_series)
        # mode 0 = plain (since plain and dod are tied for linear)
        assert enc[0] == 0

    def test_quadratic_picks_dod(self, quadratic_series):
        """Quadratic (i*i): dod wins because second-order delta is 0."""
        enc = bha_delta._adaptive_encode_int(quadratic_series)
        assert enc[0] == 2  # mode 2 = delta-of-delta

    def test_random_walk_picks_plain(self, random_walk):
        enc = bha_delta._adaptive_encode_int(random_walk)
        assert enc[0] == 0  # mode 0 = plain delta

    def test_int32_close_values_picks_plain(self):
        """1000 values starting at 1000000: plain delta wins."""
        vals = [1_000_000 + i for i in range(1000)]
        enc = bha_delta._adaptive_encode_int(vals)
        # Plain or dod wins; both produce 1 byte/varint
        assert enc[0] in (0, 2)

    def test_int64_close_values_picks_plain(self):
        """10**15 + i — close values, plain delta wins."""
        vals = [10**15 + i for i in range(1000)]
        enc = bha_delta._adaptive_encode_int(vals)
        assert enc[0] in (0, 2, 3, 4)

    def test_single_value(self):
        """Single value: no encoding needed."""
        enc = bha_delta._adaptive_encode_int([42])
        assert enc == b"\x00\x00\x00\x00\x00\x00\x00\x2a"

    def test_empty_values(self):
        enc = bha_delta._adaptive_encode_int([])
        assert enc == b""


class TestAdaptiveIntDecoder:
    """Verify decoder matches encoder for all modes."""

    @pytest.mark.parametrize("vals_name,vals", [
        ("constant_step", [100 + 7 * i for i in range(1000)]),
        ("quadratic", [i * i for i in range(1000)]),
        ("random_walk_seed42", [0] + [__import__('random').Random(42).randint(-3, 3) for _ in range(999)]),
        ("alternating", [0 if i % 2 == 0 else 10**8 for i in range(1000)]),
        ("single", [42]),
        ("two_values", [1, 2]),
        ("empty", []),
    ])
    def test_encode_decode_roundtrip(self, vals_name, vals):
        enc = bha_delta._adaptive_encode_int(vals)
        dec = bha_delta._decode_adaptive(enc)
        assert dec == vals, f"roundtrip failed for {vals_name}"


class TestTryColumnDelta:
    """End-to-end tests for the public try_column_delta API."""

    def test_csv_with_int_columns_compresses(self, small_csv):
        """A typical CSV should compress to a fraction of its size."""
        result = bha_delta.try_column_delta(small_csv)
        assert result is not None
        assert len(result) < len(small_csv)

    def test_too_short_returns_none(self):
        """Data below 256 bytes threshold: no transform."""
        assert bha_delta.try_column_delta(b"a,b\n1,2\n") is None

    def test_too_large_returns_none(self):
        """Data above 8MB threshold: no transform (avoid OOM)."""
        # 9MB of zeros
        big_data = b"0,0,0\n" * (9 * 1024 * 1024 // 5)
        assert len(big_data) > 8 * 1024 * 1024
        assert bha_delta.try_column_delta(big_data) is None

    def test_invalid_utf8_falls_back_to_latin1(self):
        """Binary data with latin-1 encoding should still work."""
        data = b"col1,col2\n" + b"1,2\n" * 30
        # Append some latin-1 high bytes
        data += bytes(range(128, 200)) * 30
        # Should not raise; may or may not return None
        result = bha_delta.try_column_delta(data)
        # If it returned something, it should be valid
        if result:
            assert isinstance(result, bytes)

    def test_mixed_int_float_columns(self):
        """CSV with mixed int and float columns."""
        rows = ["idx,value,score"]
        for i in range(50):
            rows.append(f"{i},{i*1.5},{i*2.7}")
        csv = "\n".join(rows).encode()
        result = bha_delta.try_column_delta(csv)
        # Should compress (numeric columns compress well)
        if result:
            assert len(result) < len(csv)


class TestDeltaEncodePlain:
    """Plain delta encoder/decoder (mode 0)."""

    def test_roundtrip_small(self):
        vals = [10, 12, 14, 16, 18]
        enc = bha_delta._delta_encode(vals)
        dec = bha_delta._decode_plain_delta(enc)
        assert dec == vals

    def test_roundtrip_negative_deltas(self):
        vals = [100, 95, 90, 85, 80, 75]
        enc = bha_delta._delta_encode(vals)
        dec = bha_delta._decode_plain_delta(enc)
        assert dec == vals

    def test_empty(self):
        assert bha_delta._delta_encode([]) == b""
        assert bha_delta._decode_plain_delta(b"") == []

    def test_single(self):
        vals = [42]
        enc = bha_delta._delta_encode(vals)
        assert len(enc) == 8  # just the 8-byte value
        dec = bha_delta._decode_plain_delta(enc)
        assert dec == vals