import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import llm, tavily_search
from app.main import app

# No `with` block: the startup hook (which needs Qdrant) is not run.
client = TestClient(app)
H = {"x-api-key": "k"}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "k")


def test_health_needs_no_key():
    assert client.get("/health").json() == {"ok": True}


def test_missing_or_wrong_key_is_401():
    assert client.post("/v1/search", json={}).status_code == 401
    assert client.post("/v1/search", json={}, headers={"x-api-key": "nope"}).status_code == 401
    assert client.get("/v1/digests").status_code == 401


def test_search_body_is_validated():
    body = {"query": "a", "department": "ml", "cohort_id": "1"}     # query too short
    assert client.post("/v1/search", json=body, headers=H).status_code == 422


def _upload(name, department="ml", **extra):
    return client.post(
        "/v1/documents", headers=H,
        files={"file": (name, b"hello world", "application/octet-stream")},
        data={"department": department, "cohort_id": "1", **extra})


def test_upload_rejects_unknown_department():
    assert _upload("a.txt", department="astrology").status_code == 400


def test_upload_rejects_unsupported_type():
    assert _upload("a.exe").status_code == 415


def test_upload_rejects_overlap_not_smaller_than_size():
    assert _upload("a.txt", chunk_size="100", chunk_overlap="100").status_code == 422


def test_digest_preview_with_mocked_providers(monkeypatch):
    monkeypatch.setattr(tavily_search, "search_web", lambda q, max_results=6: {
        "results": [{"url": f"https://s{i}.org/x", "title": f"T{i}", "content": "c", "score": 1}
                    for i in range(3)],
        "images": []})

    def fake_llm(prompt, **kw):
        if prompt.startswith("TASK: PLAN_QUERIES"):
            return {"queries": ["a b c"]}
        return {"headline": "H", "intro": "I", "items": [
            {"source_id": i, "title": f"T{i}", "summary": "s", "why_relevant": "w"}
            for i in range(3)]}

    monkeypatch.setattr(llm, "generate_json", fake_llm)
    r = client.post("/v1/digests/preview", headers=H, json={"department": "ml", "location": "Bamenda"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and len(body["items"]) == 3
    assert body["segment_id"] == "preview__ml__bamenda"


def test_docs_can_be_hidden(monkeypatch):
    import importlib
    import app.main as main
    monkeypatch.setattr(settings, "enable_docs", False)
    hidden = TestClient(importlib.reload(main).app)
    assert hidden.get("/docs").status_code == 404
    assert hidden.get("/openapi.json").status_code == 404
    assert hidden.get("/health").json() == {"ok": True}
    monkeypatch.setattr(settings, "enable_docs", True)
    importlib.reload(main)
