"""Tests for PASS021 runtime semantics: AutoSwitch, Deal Radar, catalog provenance."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Redirect runtime artifact paths to a temp dir (no pollution)."""
    monkeypatch.setattr(runtime, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runtime, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(runtime, "GRAPH_PATH", tmp_path / "graph.json")
    monkeypatch.setattr(runtime, "SNAPSHOT_DIR", tmp_path / "snapshots")
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    runtime._SEQ["value"] = 0
    return tmp_path


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


# --- PASS022: regression — signed verify + migration/rollback + durable core coexist ---

def test_security_and_durable_core_coexist():
    """PASS022 P0: FIX2 durable core must NOT have removed the security layer,
    and vice versa. Both feature sets must be importable and callable."""
    # durable core (FIX2)
    assert hasattr(runtime, "run_dir")
    assert hasattr(runtime, "read_run_result")
    assert hasattr(runtime, "read_run_events")
    assert hasattr(runtime, "next_seq")
    assert runtime.RUN_CREATED == "CREATED"
    assert runtime.ALLOWED_ORIGINS
    # security layer (Ed25519 + migration/rollback)
    assert callable(runtime.verify_integrity)
    assert callable(runtime.snapshot_state)
    assert callable(runtime.migrate_state)
    assert callable(runtime.rollback_state)
    assert runtime.MANIFEST_PATH
    assert runtime.PUBLIC_KEY_HEX
    # PASS021 semantics
    assert callable(runtime.decide_switch)
    assert callable(runtime.deal_radar)
    assert callable(runtime.observed_catalog)


def test_integrity_ok_fail_closed():
    ok, err = runtime.verify_integrity()
    # integrity must be OK against the freshly re-signed MANIFEST (PASS022 §2)
    assert ok, err


def test_signed_verify_and_run_coexist(isolated, monkeypatch):
    """A signed-update check does not disturb a durable run's per-run artifacts."""
    def fake(provider, model, messages, temperature=0.7):
        return {"content": "OK", "latency_ms": 3}
    monkeypatch.setattr(runtime, "chat", fake)
    ok, _ = runtime.verify_integrity()
    assert ok
    r = runtime.run({"model": "qwen2.5:14b", "prompt": "x"})
    assert runtime.read_run_result(r["run_id"])["status"] == "ok"
    assert runtime.read_run_state(r["run_id"])["status"] == "SUCCEEDED"
