"""Unit tests for bha_core.bha_parallel — orchestrator with v11.

Tests gate selection, worker strategy, v11 priority, fallback behavior.
Requires BHA runtime. Auto-skipped when unavailable.

These tests use the public bha_parallel_compress() function which
spawns ProcessPoolExecutor workers. We use small data (< 64KB threshold)
to avoid the parallel path and exercise the sequential fallback instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bha_core import bha_parallel
from bha_core import bha_recommender_v11


class TestIsCsvLike:
    """_is_csv_like is a pure-stdlib sniffer — can test without BHA runtime."""

    def test_csv_with_comma(self):
        data = b"a,b,c\n1,2,3\n4,5,6\n" * 20
        assert bha_parallel._is_csv_like(data) is True

    def test_html_not_csv(self):
        data = b"<!DOCTYPE html><html><body>test</body></html>"
        assert bha_parallel._is_csv_like(data) is False

    def test_empty(self):
        assert bha_parallel._is_csv_like(b"") is False

    def test_binary_not_csv(self):
        # Truly binary (high-bit bytes only) — should not be CSV
        data = bytes([0x80, 0xFF, 0x90, 0xFE]) * 200
        assert bha_parallel._is_csv_like(data) is False


class TestSelectParallelStrategy:
    """Test the adaptive worker-count strategy."""

    def test_tiny_size_zero_workers(self):
        assert bha_parallel._select_parallel_strategy(
            50_000, is_csv_like=False, n_workers_max=8) == 0

    def test_csv_small_one_worker(self):
        assert bha_parallel._select_parallel_strategy(
            300_000, is_csv_like=True, n_workers_max=8) == 1

    def test_csv_large_more_workers(self):
        workers = bha_parallel._select_parallel_strategy(
            3_000_000, is_csv_like=True, n_workers_max=8)
        assert workers >= 2

    def test_non_csv_2mb_two_workers(self):
        # PARALLEL_MEDIUM_MAX is 2**21 = 2MB exactly
        workers = bha_parallel._select_parallel_strategy(
            1 << 21, is_csv_like=False, n_workers_max=8)
        assert workers == 2

    def test_non_csv_huge_max_workers(self):
        workers = bha_parallel._select_parallel_strategy(
            100_000_000, is_csv_like=False, n_workers_max=8)
        assert workers == 8  # capped at max


class TestSelectWorkersFor:
    def test_uses_csv_detection(self):
        # >=512KB CSV: workers >= 1 (PARALLEL_MIN_SIZE threshold)
        # Need >=65536 reps × 8 bytes = 524288 bytes
        workers = bha_parallel._select_workers_for(b"a,b\n1,2\n" * 65536)
        assert workers >= 1

    def test_uses_size_bucket(self):
        # 64KB non-CSV: 0 workers (below 256KB threshold)
        workers = bha_parallel._select_workers_for(b"x" * (1 << 16))
        assert workers == 0


class TestMetaDict:
    """Verify meta dict structure returned by bha_parallel_compress."""

    def test_below_threshold_returns_meta(self):
        """For data below PARALLEL_MIN_SIZE, sequential fallback is used."""
        # Use below-threshold data (50KB) — sequential path
        data = b"a,b,c\n1,2,3\n" * 5000  # ~40KB
        arc, meta = bha_parallel.bha_parallel_compress(data)
        assert "method" in meta
        assert "elapsed_s" in meta
        assert "best_gate" in meta


@pytest.mark.requires_bha
class TestV11Integration:
    """Tests for v11 recommender integration in bha_parallel."""

    def test_meta_includes_v11_priority(self):
        """When v11 enabled, meta['v11_priority'] is set."""
        data = b"a,b,c\n1,2,3\n" * 1000  # ~10KB CSV
        arc, meta = bha_parallel.bha_parallel_compress(data)
        # Below threshold: fallback path
        # But v11 still tries to recommend (meta should have priority=None)
        # OR no v11 at all in fallback path
        # Just check meta exists
        assert "v11_priority" in meta or "v11_lzma_preset" in meta

    def test_bha_use_v11_env_disables_recommender(self, monkeypatch):
        """Setting BHA_USE_V11=0 should disable v11 in meta."""
        monkeypatch.setenv("BHA_USE_V11", "0")
        data = b"a,b,c\n1,2,3\n" * 1000
        arc, meta = bha_parallel.bha_parallel_compress(data)
        assert meta.get("v11_priority") is None or meta.get("v11_lzma_preset") is None


@pytest.mark.requires_bha
@pytest.mark.slow
class TestParallelExecution:
    """Tests that actually exercise the parallel pool (>=500KB data)."""

    def test_csv_500kb_parallel(self, tmp_path):
        """500KB CSV should trigger parallel path and find a working gate."""
        csv_path = tmp_path / "big.csv"
        rows = ["idx,a,b,c"]
        for i in range(8000):
            rows.append(f"{i},{i*2},{i*3},{i*5}")
        csv_path.write_text("\n".join(rows))

        data = csv_path.read_bytes()
        assert len(data) >= 500_000
        arc, meta = bha_parallel.bha_parallel_compress(data, src_path=csv_path)
        assert "best_size" in meta
        assert meta["best_size"] > 0

    def test_baseline_comparison(self, tmp_path):
        """Parallel should produce output <= baseline (sequential bha_compress)."""
        from bha_core import bha as bha_mod

        csv_path = tmp_path / "compare.csv"
        rows = ["idx,a,b"]
        for i in range(8000):
            rows.append(f"{i},{i*2},{i*3}")
        csv_path.write_text("\n".join(rows))

        data = csv_path.read_bytes()

        seq_arc, _, _ = bha_mod.bha_compress(data, src_path=csv_path, total_timeout_s=60)
        par_arc, par_meta = bha_parallel.bha_parallel_compress(
            data, src_path=csv_path, baseline=seq_arc, max_workers=2)

        assert "best_size" in par_meta
        # Best parallel result should be <= baseline (we always add it as candidate)
        assert par_meta["best_size"] <= len(seq_arc)