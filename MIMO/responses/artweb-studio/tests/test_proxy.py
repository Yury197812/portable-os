"""API tests for the ArtWeb Studio proxy (playground_proxy.py, :8890)."""
import requests

PROXY = "http://127.0.0.1:8890"


def test_health():
    r = requests.get(f"{PROXY}/api/health", timeout=15)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_models_list():
    r = requests.get(f"{PROXY}/api/models", timeout=15)
    assert r.status_code == 200
    assert len(r.json()) >= 5


def test_catalog_400_models():
    r = requests.get(f"{PROXY}/api/catalog", timeout=20)
    assert r.status_code == 200
    assert len(r.json()) == 400


def test_skills_registry():
    r = requests.get(f"{PROXY}/api/skills", timeout=20)
    assert r.status_code == 200
    assert len(r.json()) >= 100


def test_openrouter_live():
    r = requests.get(f"{PROXY}/api/openrouter", timeout=40)
    assert r.status_code == 200
    assert len(r.json()["data"]) > 100


def test_reviews_crud():
    model = "gpt-4o-mini"
    # create
    r = requests.post(
        f"{PROXY}/api/reviews",
        json={"model": model, "author": "pytest", "rating": 5, "text": "automated test review"},
        timeout=15,
    )
    assert r.status_code in (200, 201)
    rid = r.json()["id"]
    # read back
    r = requests.get(f"{PROXY}/api/reviews?model={model}", timeout=15)
    assert any(x["id"] == rid for x in r.json()["reviews"])
    # delete
    r = requests.delete(f"{PROXY}/api/reviews/{rid}", timeout=15)
    assert r.status_code == 200
    # gone
    r = requests.get(f"{PROXY}/api/reviews?model={model}", timeout=15)
    assert all(x["id"] != rid for x in r.json()["reviews"])


def test_reviews_validation():
    # rating out of range
    r = requests.post(f"{PROXY}/api/reviews", json={"model": "x", "rating": 0, "text": "y"}, timeout=15)
    assert r.status_code == 400
    # missing text
    r = requests.post(f"{PROXY}/api/reviews", json={"model": "x", "rating": 4}, timeout=15)
    assert r.status_code == 400
    # missing model
    r = requests.post(f"{PROXY}/api/reviews", json={"rating": 4, "text": "y"}, timeout=15)
    assert r.status_code == 400
