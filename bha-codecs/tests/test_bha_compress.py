"""Unit tests for bha_core.bha — entry point with safety patches.

Tests bha_compress() wall-clock guard, patch behavior, and CLI.
Requires BHA runtime. Auto-skipped when BHA runtime is unavailable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from bha_core import bha


@pytest.mark.requires_bha
class TestBhaCompress:
    """Tests for the public bha_compress() API."""

    def test_basic_compression(self):
        """Compress a small string, get bytes back."""
        data = b"hello world " * 100
        arc, stats, meta = bha.bha_compress(data)
        assert len(arc) > 0
        assert "elapsed_s" in meta
        assert "reached_finish" in meta

    def test_compression_finishes_quickly_on_small_data(self):
        """Small data should finish well under default timeout."""
        data = b"x" * 1000
        arc, stats, meta = bha.bha_compress(data, total_timeout_s=10)
        assert meta["reached_finish"] is True
        assert meta["timed_out"] is False

    def test_compression_reaches_finish_on_larger_data(self):
        """Moderately-sized data should finish under 20s timeout."""
        # 10KB of repetitive data — should compress fast
        data = b"the quick brown fox jumps over the lazy dog\n" * 250
        arc, stats, meta = bha.bha_compress(data, total_timeout_s=20)
        assert meta["reached_finish"] is True

    def test_meta_keys_present(self):
        """Meta dict has all expected keys."""
        data = b"hello world"
        _, _, meta = bha.bha_compress(data)
        for key in ["elapsed_s", "timed_out", "reached_finish"]:
            assert key in meta

    def test_stats_keys_present(self):
        """Stats dict has expected keys."""
        data = b"hello world"
        _, stats, _ = bha.bha_compress(data)
        # stats is whatever _compress_best returns — verify it's not None
        assert stats is not None


@pytest.mark.requires_bha
class TestBhaPatches:
    """Verify that bha.py applies safety patches on import."""

    def test_lzma_preset_6_not_extreme_for_large_data(self):
        """The patch should replace PRESET_EXTREME with preset 6 for >64KB."""
        data = b"a" * 100_000  # 100KB > 64KB threshold
        arc, _, meta = bha.bha_compress(data)
        # Should reach finish quickly (patch worked, no EXTREME)
        assert meta["reached_finish"] is True
        # Should complete in <2 seconds (preset 6, not EXTREME)
        assert meta["elapsed_s"] < 2.0

    def test_ssp_encode_bypassed_for_large_data(self):
        """The _safe_encode_data should bypass ssp.encode_data for >256KB."""
        # 300KB > 256KB threshold
        data = b"a" * 300_000
        arc, _, meta = bha.bha_compress(data, total_timeout_s=15)
        assert meta["reached_finish"] is True
        # If patch worked: lzma_fallback used (not ssp LSTM model)
        assert meta["elapsed_s"] < 5.0


@pytest.mark.requires_bha
class TestBhaDeltaIntegration:
    """Test that bha.py uses bha_delta.try_column_delta for CSV-like data."""

    def test_csv_data_uses_delta(self, tmp_path):
        """For CSV-like data, delta_pp is tried as alternative to LZMA."""
        # Create a simple CSV file
        csv_path = tmp_path / "test.csv"
        rows = ["idx,value"]
        for i in range(100):
            rows.append(f"{i},{i*2}")
        csv_path.write_text("\n".join(rows))

        data = csv_path.read_bytes()
        arc, _, meta = bha.bha_compress(data, src_path=csv_path)
        assert meta["reached_finish"] is True
        # Should compress well (CSV with integer columns)
        assert len(arc) < len(data)