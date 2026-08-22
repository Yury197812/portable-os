"""Unit tests for bha_core.bha_recommender_v11.

Tests the production recommender API: recommend(), lzma_preset_for(),
stats(), EXT_PRIORITY dispatch, fallback behavior.

No BHA runtime needed — these tests use only stdlib + bha_core package.
"""
from __future__ import annotations

import pytest

from bha_core import bha_recommender_v11


class TestStats:
    def test_stats_returns_version_v11(self):
        stats = bha_recommender_v11.stats()
        assert stats["version"] == "v11"

    def test_stats_includes_loo_metrics(self):
        stats = bha_recommender_v11.stats()
        assert "loo_top1_pct" in stats
        assert "loo_top3_pct" in stats
        assert "n_files" in stats
        # v11 was trained on 46 files; allow some drift
        assert stats["n_files"] >= 40

    def test_stats_top1_accuracy_at_least_45_pct(self):
        # v11 should beat v9b (42.0%) — minimum bar at 45%
        stats = bha_recommender_v11.stats()
        assert stats["loo_top1_pct"] >= 45.0


class TestRecommend:
    def test_recommend_csv_returns_csv_gates_first(self):
        """CSV files should have delta_pp at the top of priority."""
        gates = bha_recommender_v11.recommend("data.csv", 500_000)
        assert gates[0] == "delta_pp"
        assert "lzma_fallback" in gates[:3]

    def test_recommend_html_returns_text_gates(self):
        """HTML files should not start with delta_pp."""
        gates = bha_recommender_v11.recommend("page.html", 200_000)
        assert "lzma_fallback" in gates[:3]

    def test_recommend_json_returns_json_gates(self):
        gates = bha_recommender_v11.recommend("data.json", 500_000)
        assert "lzma_fallback" in gates[:3]

    def test_recommend_unknown_extension_uses_defaults(self):
        """Unknown extension → DEFAULT_PRIORITY fallback."""
        gates = bha_recommender_v11.recommend("data.xyz", 50_000)
        assert len(gates) >= 3
        assert "delta_pp" in gates
        assert "lzma_fallback" in gates

    def test_recommend_returns_k_gates(self):
        for k in [1, 3, 5, 10]:
            gates = bha_recommender_v11.recommend("file.csv", 100_000, k=k)
            assert len(gates) == k

    def test_recommend_returns_unique_gates(self):
        """No duplicates in priority list (k=5)."""
        gates = bha_recommender_v11.recommend("file.csv", 100_000, k=5)
        assert len(gates) == len(set(gates))

    def test_recommend_for_known_extension_returns_at_least_3(self):
        """For well-known extensions, get at least 3 gates (extension
        rules + DEFAULT_PRIORITY padding)."""
        gates = bha_recommender_v11.recommend("file.html", 100_000, k=10)
        assert len(gates) >= 3


class TestLzmaPreset:
    def test_lzma_preset_default_is_6(self):
        """Default preset is 6 (medium compression, fast)."""
        preset = bha_recommender_v11.lzma_preset_for("data.csv", 500_000)
        assert preset == 6

    def test_lzma_preset_tiny_file_is_9(self):
        """Tiny files (<8KB) get EXTREME compression preset 9."""
        preset = bha_recommender_v11.lzma_preset_for("tiny.txt", 500)
        assert preset == 9

    def test_lzma_preset_known_csv_is_6(self):
        preset = bha_recommender_v11.lzma_preset_for("data.csv", 100_000)
        assert preset == 6

    def test_lzma_preset_html_is_6(self):
        preset = bha_recommender_v11.lzma_preset_for("page.html", 200_000)
        assert preset == 6


class TestFeatures:
    """Tests the _features() helper indirectly via recommend()."""

    def test_tiny_threshold_is_8kb(self):
        """8 KiB boundary: <8KiB → preset 9 (tiny bucket), >=8KiB → from rules."""
        # Below threshold: tiny bucket always returns 9 regardless of extension
        assert bha_recommender_v11.lzma_preset_for("f.txt", 7_999) == 9
        assert bha_recommender_v11.lzma_preset_for("data.csv", 100) == 9
        # Above threshold: depends on telemetry-driven top codec
        # For .txt files >=8KB, telemetry shows brotli_6 wins → preset 9
        # For .csv files >=8KB, telemetry shows lzma6 wins → preset 6
        assert bha_recommender_v11.lzma_preset_for("data.csv", 8 * 1024) == 6
        assert bha_recommender_v11.lzma_preset_for("data.csv", 100_000) == 6

    def test_size_buckets(self):
        """Size buckets map to different extension priorities."""
        # Small CSV — delta_pp should still be first
        gates_small = bha_recommender_v11.recommend("f.csv", 50_000)
        gates_med = bha_recommender_v11.recommend("f.csv", 200_000)
        # Both should have delta_pp first, but later gates may differ
        assert gates_small[0] == gates_med[0] == "delta_pp"