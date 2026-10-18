import json
import re
import time
from functools import lru_cache

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.gemini_api_key)


def _parse(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    return json.loads(text)


def generate_json(prompt: str, temperature: float = 0.3, max_retries: int = 6) -> dict:
    """Gemini call that must return a JSON object. Backs off on 429/5xx and retries bad JSON."""
    if settings.mock_mode:
        if prompt.startswith("TASK: PLAN_QUERIES"):
            return {"queries": ["ml internships", "ai hackathon",
                                "data science scholarships", "tech conference"]}
        from datetime import date, timedelta
        d = (date.today() + timedelta(days=30)).isoformat()
        return {"headline": "Mock weekly digest", "intro": "Sample intro.", "items": [
            {"source_id": i, "title": f"Sample opportunity {i}", "summary": "Sample summary.",
             "why_relevant": "Matches the group's skills.", "category": "hackathon",
             "deadline": d, "image_id": 0 if i == 0 else None,
             "image_caption": "Students at a hackathon" if i == 0 else None}
            for i in range(4)]}
    bad_json = 0
    for attempt in range(max_retries):
        try:
            res = _client().models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            return _parse(res.text)
        except APIError as e:
            if e.code in (429, 500, 503) and attempt < max_retries - 1:
                time.sleep(min(5 * 2 ** attempt, 65))
                continue
            raise
        except json.JSONDecodeError:
            bad_json += 1
            if bad_json >= 3:
                raise
    raise RuntimeError("LLM did not return valid JSON")
