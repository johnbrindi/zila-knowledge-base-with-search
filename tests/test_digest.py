import fakeredis
import pytest

from app.core import digest_agent, digest_store as store, llm, tavily_search
from app.core.profiles import Profile, segment_profiles

SEG = {"segment_id": "ml__bamenda", "department": "ml", "location": "bamenda", "size": 6,
       "top_skills": ["python"], "top_interests": ["nlp"], "levels": ["beginner"]}


def fake_search(query, max_results=6):
    return {
        "results": [{"url": f"https://site{i}.org/opp", "title": f"Opp {i}",
                     "content": "details", "score": 1 - i / 10} for i in range(5)],
        "images": [{"url": "https://img.site0.org/a.jpg", "description": "students at a hackathon"}],
    }


def fake_llm(prompt, **kw):
    if prompt.startswith("TASK: PLAN_QUERIES"):
        return {"queries": ["ml internships cameroon", "ai hackathon africa"]}
    return {"headline": "Your week in ML", "intro": "Hi. Here you go.", "items": [
        {"source_id": 0, "title": "Good one", "summary": "s", "why_relevant": "w",
         "category": "hackathon", "deadline": "2999-01-01", "image_id": 0, "image_caption": "Hackers"},
        {"source_id": 1, "title": "Expired", "summary": "s", "why_relevant": "w",
         "deadline": "2001-01-01"},
        {"source_id": 99, "title": "Hallucinated source", "summary": "s", "why_relevant": "w"},
        {"source_id": 2, "title": "Bad image id", "summary": "s", "why_relevant": "w",
         "category": "weird", "image_id": 42},
        {"source_id": 3, "title": "No deadline", "summary": "s", "why_relevant": "w"},
        {"source_id": 0, "title": "Duplicate url", "summary": "s", "why_relevant": "w"},
    ]}


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    monkeypatch.setattr(tavily_search, "search_web", fake_search)
    monkeypatch.setattr(llm, "generate_json", fake_llm)
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(store, "r", fake)


def test_digest_validation():
    d = digest_agent.build_digest(SEG, "2026-W42", seen_urls={"https://site3.org/opp"})
    titles = [i["title"] for i in d["items"]]
    # expired, hallucinated and duplicate items dropped; already-seen site3 never reaches the LLM
    assert titles == ["Good one", "Bad image id", "No deadline"]
    assert all(i["url"] != "https://site3.org/opp" for i in d["items"])
    assert d["items"][0]["image_url"] == "https://img.site0.org/a.jpg"
    assert d["items"][1]["image_url"] is None and d["items"][1]["category"] == "other"
    assert all(i["url"].startswith("https://site") for i in d["items"])
    assert d["items"][0]["deadline"] == "2999-01-01"
    assert "![Hackers](" in d["markdown"] and "Image via img.site0.org" in d["markdown"]


def test_segmentation_merges_small_groups():
    ps = [Profile(str(i), "ml", ["python"], [], None, "Bamenda") for i in range(6)]
    ps += [Profile("x1", "ml", [], [], None, "Douala"), Profile("x2", "web", [], [], None, "Douala")]
    segs = {s.segment_id: s for s in segment_profiles(ps)}
    assert segs["ml__bamenda"].size == 6
    assert segs["ml__any"].student_ids == ["x1"]          # small group folded into dept-wide
    assert "student_ids" not in segs["ml__bamenda"].public()


def test_task_end_to_end():
    from app.worker.digest_tasks import build_segment_digest
    store.save_segment_students("ml__bamenda", ["s1", "s2"])
    store.init_run("2026-W42", 1)
    out = build_segment_digest.apply(args=[SEG, "2026-W42", False]).get()
    assert out["status"] == "published"
    assert store.get_digest("2026-W42", "ml__bamenda")["status"] == "published"
    assert store.student_segment("s1") == "ml__bamenda"
    assert "https://site0.org/opp" in store.get_seen("ml__bamenda")
    assert store.run_status("2026-W42")["done"] == "1"
