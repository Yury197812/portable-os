"""Tests for PASS021 runtime semantics: AutoSwitch, Deal Radar, catalog provenance."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


def test_decide_switch_free_first():
    d = runtime.decide_switch("FREE", False, 100)
    assert d["ok"] is True
    assert d["chosen"] == "FREE"


def test_decide_switch_free_exhausted_unknown():
    # free_remaining == None → treated as exhausted (no fake availability)
    d = runtime.decide_switch("FREE", False, None)
    assert d["ok"] is False


def test_decide_switch_paid_owned():
    d = runtime.decide_switch("PAID_OWNED", True, None)
    assert d["ok"] is True
    assert d["chosen"] == "PAID_OWNED"


def test_decide_switch_unowned_paid_deny():
    d = runtime.decide_switch("PAID_UNOWNED", False, None)
    assert d["ok"] is False
    assert "DENY" in d["reason"]


def test_deal_radar_official_registry():
    registry = list(runtime.OFFICIAL_SOURCES.keys())
    for p in ("OpenAI", "Anthropic", "Gemini", "OpenRouter", "Groq", "Mistral", "xAI"):
        assert p in registry
    deals = runtime.deal_radar()
    # xAI batch applies only to listed selectors
    xai = next(d for d in deals if d["id"] == "xai-batch-20")
    assert xai["status"] == "VERIFIED"
    assert "grok-beta" in xai["applies_to"]
    # Groq Flex is NOT a discount
    groq = next(d for d in deals if d["id"] == "groq-flex")
    assert "НЕ скидка" in groq["detail"]
    # user deal is UNVERIFIED
    user = next(d for d in deals if d["id"] == "user-deal-sample")
    assert user["status"] == "UNVERIFIED"


def test_observed_catalog_live_only():
    cat = runtime.observed_catalog()
    assert cat["scope"]
    for e in cat["entities"]:
        assert e["provenance"] == "LIVE"
        assert e["routing_ready"] is True
        # config-only caps are NOT VERIFIED unless actually probed
        assert e["cap_verification"] in ("CONFIG", "VERIFIED")


def test_xai_batch_scoped():
    assert "grok-beta" in runtime.XAI_BATCH_20_SELECTORS
    assert "grok-3" not in runtime.XAI_BATCH_20_SELECTORS
    assert "batch" in runtime.SOURCE_BACKED_MODES
