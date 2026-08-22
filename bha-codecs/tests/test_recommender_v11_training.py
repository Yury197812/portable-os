"""Unit tests for bha_core.recommender_v11 — L15 training script.

Tests features_of(), load_telemetry(), score_codec(), evaluate().
These are pure stdlib + JSON — no BHA runtime needed.
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from bha_core import recommender_v11


class TestFeaturesOf:
    def test_csv_features(self):
        feats = recommender_v11.features_of("data.csv", 100_000)
        assert feats["ext"] == "csv"
        assert feats["size_bucket"] == "medium"
        # size_log is rounded to 1 decimal, so 16.6096 → 16.6
        assert feats["size_log"] == 16.6

    def test_unknown_extension(self):
        feats = recommender_v11.features_of("blob", 50_000)
        assert feats["ext"] == "none"
        assert feats["size_bucket"] == "small"

    def test_size_buckets(self):
        # tiny <8KB, small <80KB, medium <400KB, large <2MB, xlarge
        assert recommender_v11.features_of("f", 100)["size_bucket"] == "tiny"
        assert recommender_v11.features_of("f", 50_000)["size_bucket"] == "small"
        assert recommender_v11.features_of("f", 200_000)["size_bucket"] == "medium"
        assert recommender_v11.features_of("f", 500_000)["size_bucket"] == "large"
        assert recommender_v11.features_of("f", 5_000_000)["size_bucket"] == "xlarge"

    def test_size_log_rounded(self):
        """size_log is rounded to 1 decimal for stable comparison."""
        feats = recommender_v11.features_of("f.csv", 100_000)
        # 100_000 log2 = 16.6096... → 16.6
        assert feats["size_log"] == round(math.log2(100_000), 1)


class TestLoadTelemetry:
    def test_load_existing_telemetry(self):
        """If telemetry_v1.json exists, load it."""
        training = recommender_v11.load_telemetry()
        if not training:
            pytest.skip("telemetry_v1.json not available (run bench_codecs.py first)")
        assert len(training) > 0
        # Each entry has the expected fields
        sample = training[0]
        assert "file" in sample
        assert "features" in sample
        assert "codec" in sample
        assert "ratio" in sample
        assert "bits_per_byte" in sample

    def test_load_skips_error_entries(self):
        """Entries with 'error' key are filtered out."""
        training = recommender_v11.load_telemetry()
        for entry in training:
            assert "error" not in entry


class TestEvaluate:
    def test_evaluate_returns_metrics_dict(self):
        """Even with empty training, evaluate returns proper structure."""
        metrics = recommender_v11.evaluate([])
        assert metrics["top1_pct"] == 0
        assert metrics["top3_pct"] == 0
        assert metrics["n"] == 0

    def test_evaluate_top1_reasonable(self):
        """If telemetry exists, top1 accuracy should be > 30% (worse than
        random codec selection)."""
        training = recommender_v11.load_telemetry()
        if len(training) < 10:
            pytest.skip("need more training data")
        metrics = recommender_v11.evaluate(training)
        # Lower bound: random codec would be ~12% (1/8 codecs)
        # v11 should be way above random
        assert metrics["top1_pct"] >= 30.0


class TestScoreCodec:
    """score_codec is internal — test through evaluate()."""

    def test_score_includes_distance_penalty(self):
        """Same extension, very different sizes → high distance."""
        training = [
            {"file": "f.csv", "features": {"ext": "csv", "size_log": 15.0},
             "codec": "lzma6", "ratio": 2.0},
        ]
        scores = recommender_v11.score_codec(
            training,
            {"ext": "csv", "size_log": 20.0},  # Very different size_log
        )
        # Should still find lzma6 but with low weight
        assert "lzma6" in scores
        # Score should be low (high distance)
        assert scores.get("lzma6", 0) < 1.0


class TestWriteRules:
    """Tests that writing rules.json produces a valid file."""

    def test_main_writes_valid_json(self, tmp_path, monkeypatch):
        """Run main() with mocked telemetry path and verify output."""
        # Telemetry has format {"rows": [{"file": ..., "codecs": [...]}]}
        fake_telemetry = {
            "rows": [
                {"file": "f.csv", "input_size": 100_000,
                 "codecs": [
                     {"codec": "lzma6", "ratio": 2.0, "bits_per_byte": 4.0,
                      "encode_p50_ms": 5.0},
                     {"codec": "brotli_11", "ratio": 1.5, "bits_per_byte": 5.3,
                      "encode_p50_ms": 7.0},
                 ]},
                {"file": "f.json", "input_size": 50_000,
                 "codecs": [
                     {"codec": "brotli_11", "ratio": 3.0, "bits_per_byte": 2.7,
                      "encode_p50_ms": 6.0},
                 ]},
            ]
        }
        fake_path = tmp_path / "fake_telemetry.json"
        fake_path.write_text(json.dumps(fake_telemetry))

        # Patch TELEMETRY path
        monkeypatch.setattr(recommender_v11, "TELEMETRY", fake_path)
        # Patch OUT path
        out_path = tmp_path / "rules.json"
        monkeypatch.setattr(recommender_v11, "OUT", out_path)

        # Run main()
        recommender_v11.main()

        # Verify rules.json was written and is valid
        assert out_path.exists()
        rules = json.loads(out_path.read_text())
        assert rules["version"] == "v11"
        assert "loo_metrics" in rules
        assert "codec_distribution" in rules