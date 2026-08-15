"""Tests for PASS024: SecretVault (secret refs only) + inventory snapshots/reconciliation."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "SNAPSHOTS_INV_DIR", tmp_path / "inventory_snapshots")
    monkeypatch.setattr(runtime, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runtime, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(runtime, "GRAPH_PATH", tmp_path / "graph.json")
    monkeypatch.setattr(runtime, "SNAPSHOT_DIR", tmp_path / "snapshots")
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    runtime._SEQ["value"] = 0
    return tmp_path


# --- SecretVault: secret refs only, no endpoint returns secret values ---

def test_vault_status_never_returns_values():
    st = runtime.vault_status()
    for p, e in st["providers"].items():
        assert "ref" in e
        # a ref is symbolic (a name / env-var NAME), never a secret VALUE
        assert e["ref"].startswith("ref:")
        # no field carries a secret value
        assert "value" not in e and "secret" not in e and "key_value" not in e


def test_local_providers_loopback_only():
    st = runtime.vault_status()
    assert st["providers"]["ollama"]["state"] == "LOCAL_LOOPBACK"
    assert st["providers"]["lmstudio"]["state"] == "LOCAL_LOOPBACK"


def test_cloud_configured_unavailable_by_default():
    st = runtime.vault_status()
    assert st["providers"]["groq"]["state"] == "CONFIGURED_UNAVAILABLE"
    assert st["providers"]["openrouter_free"]["state"] == "CONFIGURED_UNAVAILABLE"


def test_bind_unbind_cloud():
    assert runtime.bind_secret("groq")["state"] == "BOUND"
    assert runtime.vault_status()["providers"]["groq"]["state"] == "BOUND"
    assert runtime.unbind_secret("groq")["ok"] is True
    assert runtime.vault_status()["providers"]["groq"]["state"] == "CONFIGURED_UNAVAILABLE"


def test_bind_local_refused():
    r = runtime.bind_secret("ollama")
    assert r["ok"] is False


# --- Inventory snapshots + reconciliation ---

def test_inventory_snapshot_immutable(isolated):
    snap = runtime.inventory_snapshot()
    assert snap["immutable"] is True
    assert snap["snapshot_id"]
    # snapshot has its own deep copy, not a live reference
    assert snap["inventory"] is not runtime._INVENTORY
    assert runtime.list_snapshots()


def test_reconcile_no_conflict(isolated):
    # a clean snapshot first
    runtime.inventory_snapshot()
    r = runtime.reconcile_inventory(runtime._INVENTORY)
    assert r["verdict"] == "CLEAN"
    assert r["snapshot_baseline"] is not None


def test_reconcile_synthetic_cannot_poison_live(isolated):
    # baseline has qwen2.5:14b as LIVE (from _INVENTORY)
    runtime.inventory_snapshot()
    # current attempts to downgrade it to SYNTHETIC
    current = {"models": {"qwen2.5:14b": {"provenance": "SYNTHETIC", "caps": [], "routing_ready": False}}}
    r = runtime.reconcile_inventory(current)
    assert r["verdict"] == "CONFLICT"
    assert any(c["key"] == "qwen2.5:14b" for c in r["conflicts"])


def test_discovered_never_implies_capabilities(isolated, monkeypatch):
    """DISCOVERED local models must have caps=[] and routing_ready=False."""
    def fake_list(url, timeout=4):
        return {"data": [{"id": "qwen3-4b-tool-use"}]}
    monkeypatch.setattr(runtime, "urlopen", lambda base, timeout=4: _Resp(fake_list(base, timeout)))
    discovered = runtime.discover_local_models()
    for d in discovered["discovered"]:
        assert d["provenance"] == "DISCOVERED"
        assert d["caps"] == []  # no capability inference from discovery
        assert d["routing_ready"] is False


class _Resp:
    def __init__(self, data):
        self._data = data
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        import json
        return json.dumps(self._data).encode()
