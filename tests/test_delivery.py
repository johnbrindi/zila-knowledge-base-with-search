import hashlib
import hmac
import json

import httpx

from app.config import settings
from app.core import delivery

DIGEST = {"segment_id": "ml__bamenda", "week": "2026-W42", "headline": "Café opportunities"}


def test_signature_is_hmac_of_raw_body(monkeypatch):
    monkeypatch.setattr(settings, "zigex_webhook_url", "https://zigex.test/hook")
    monkeypatch.setattr(settings, "zigex_webhook_secret", "s3cret")
    seen = {}

    def fake_post(url, content, headers, timeout):
        seen.update(url=url, body=content, headers=headers)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    assert delivery.push_digest(DIGEST, ["s1", "s2"]) is True
    expected = "sha256=" + hmac.new(b"s3cret", seen["body"], hashlib.sha256).hexdigest()
    assert seen["headers"]["X-Zigex-Signature"] == expected
    payload = json.loads(seen["body"])
    assert payload["event"] == "weekly_digest"
    assert payload["student_ids"] == ["s1", "s2"]
    assert payload["digest"]["headline"] == "Café opportunities"     # non-ASCII survives


def test_no_webhook_url_means_no_delivery(monkeypatch):
    monkeypatch.setattr(settings, "zigex_webhook_url", "")
    assert delivery.push_digest(DIGEST, []) is False


def test_retries_three_times_then_gives_up(monkeypatch):
    monkeypatch.setattr(settings, "zigex_webhook_url", "https://zigex.test/hook")
    monkeypatch.setattr(delivery.time, "sleep", lambda s: None)
    calls = []

    def failing_post(url, content, headers, timeout):
        calls.append(1)
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(delivery.httpx, "post", failing_post)
    assert delivery.push_digest(DIGEST, ["s1"]) is False
    assert len(calls) == 3


def test_non_2xx_counts_as_failure(monkeypatch):
    monkeypatch.setattr(settings, "zigex_webhook_url", "https://zigex.test/hook")
    monkeypatch.setattr(delivery.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        delivery.httpx, "post",
        lambda url, content, headers, timeout: httpx.Response(
            401, request=httpx.Request("POST", url)))
    assert delivery.push_digest(DIGEST, ["s1"]) is False
