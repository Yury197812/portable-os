"""Tests for PASS023: persisted workflow DAG execution + SUBWORKFLOW lineage."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runtime, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(runtime, "GRAPH_PATH", tmp_path / "graph.json")
    monkeypatch.setattr(runtime, "SNAPSHOT_DIR", tmp_path / "snapshots")
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    runtime._SEQ["value"] = 0
    # default graph: validate -> route -> execute -> record
    (tmp_path / "graph.json").write_text(
        '{"id":"g","nodes":[{"id":"validate"},{"id":"route"},{"id":"execute"},{"id":"record"}],'
        '"edges":[{"from":"validate","to":"route"},{"from":"route","to":"execute"},{"from":"execute","to":"record"}]}',
        encoding="utf-8",
    )
    return tmp_path


def _fake_chat(monkeypatch, content="OK", latency_ms=5):
    def fake(provider, model, messages, temperature=0.7):
        return {"content": content, "latency_ms": latency_ms}
    monkeypatch.setattr(runtime, "chat", fake)


def test_topo_sort():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
    assert runtime.topo_sort(nodes, edges) == ["a", "b", "c"]


def test_topo_sort_cycle_rejected():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]
    with pytest.raises(RuntimeError):
        runtime.topo_sort(nodes, edges)


def test_run_dag_executes_persisted_graph(isolated, monkeypatch):
    _fake_chat(monkeypatch)
    result = runtime.run_dag({"model": "qwen2.5:14b", "prompt": "hi"})
    assert result["status"] == "ok"
    rid = result["run_id"]
    # nodes executed in topological order: all four terminal SUCCEEDED
    st = runtime.read_run_state(rid)
    assert st["status"] == "SUCCEEDED"
    for n in ("validate", "route", "execute", "record"):
        assert st["nodes"][n] == "SUCCEEDED"
    # events carry monotonic seq
    seqs = [e["seq"] for e in runtime.read_run_events(rid)]
    assert seqs == sorted(seqs)


def test_run_dag_custom_graph(isolated, monkeypatch):
    """A DIFFERENT persisted DAG (validate -> execute only) is executed, not the fixed 4-step."""
    _fake_chat(monkeypatch)
    (isolated / "graph.json").write_text(
        '{"id":"custom","nodes":[{"id":"validate"},{"id":"execute"}],'
        '"edges":[{"from":"validate","to":"execute"}]}',
        encoding="utf-8",
    )
    result = runtime.run_dag({"model": "qwen2.5:14b", "prompt": "hi"})
    assert result["status"] == "ok"
    st = runtime.read_run_state(result["run_id"])
    # only validate + execute ran; route/record absent
    assert set(st["nodes"].keys()) == {"validate", "execute"}


def test_subworkflow_lineage(isolated, monkeypatch):
    _fake_chat(monkeypatch)
    parent = runtime.run_subworkflow(
        {"model": "qwen2.5:14b", "prompt": "parent"},
        [
            {"model": "qwen2.5:14b", "prompt": "child1"},
            {"model": "qwen2.5:14b", "prompt": "child2"},
        ],
    )
    assert parent["status"] == "ok"
    assert "subworkflow" in parent
    child_ids = [c["run_id"] for c in parent["subworkflow"]["child_run_ids"]]
    assert len(child_ids) == 2

    # lineage: children point back to parent
    for cid in child_ids:
        assert runtime.read_run_state(cid)["parent_run_id"] == parent["run_id"]

    # read_lineage(parent) -> descendants = both children
    lineage = runtime.read_lineage(parent["run_id"])
    assert set(lineage["descendants"]) == set(child_ids)
    # read_lineage(child) -> ancestors = parent
    clineage = runtime.read_lineage(child_ids[0])
    assert clineage["ancestors"] == [parent["run_id"]]


def test_failed_subworkflow_persists_lineage(isolated, monkeypatch):
    def boom(provider, model, messages, temperature=0.7):
        raise RuntimeError("down")
    monkeypatch.setattr(runtime, "chat", boom)
    parent = runtime.run_subworkflow({"model": "qwen2.5:14b", "prompt": "x"}, [])
    assert parent["status"] == "error"
    # failed parent still records empty subworkflow lineage
    assert parent["subworkflow"]["child_run_ids"] == []
