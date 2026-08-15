"""Unit tests for provider circuit-breaker / backoff state (playground_proxy)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import playground_proxy as pp  # noqa: E402


def test_circuit_breaker_opens_and_closes():
    pp.provider_ok("t_prov")
    assert pp.provider_available("t_prov")
    pp.provider_fail("t_prov", "boom")
    assert not pp.provider_available("t_prov")
    st = pp.provider_status()["t_prov"]
    assert st["consec_failures"] == 1
    assert st["cooling_down"] is True
    assert st["last_error"] == "boom"
    pp.provider_ok("t_prov")
    assert pp.provider_available("t_prov")
    assert pp.provider_status()["t_prov"]["consec_failures"] == 0


def test_backoff_grows_exponentially():
    pp.provider_ok("t_prov2")
    pp.provider_fail("t_prov2", "x")
    r1 = pp.provider_status()["t_prov2"]["retry_in_s"]
    pp.provider_fail("t_prov2", "x")
    r2 = pp.provider_status()["t_prov2"]["retry_in_s"]
    assert r2 > r1  # 2nd failure -> longer backoff (2s -> 4s)
