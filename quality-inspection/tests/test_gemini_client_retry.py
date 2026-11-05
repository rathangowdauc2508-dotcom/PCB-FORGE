from __future__ import annotations

import pytest

from app.gemini_client import GeminiService


def test_invalid_key_does_not_block_next_configured_key(monkeypatch):
    service = GeminiService(api_keys=["bad-key", "good-key"], request_timeout_sec=1)
    tried: list[str] = []

    class FakeClient:
        def __init__(self, key: str):
            self.key = key

    monkeypatch.setattr(service, "_client_for_key", FakeClient)

    def operation(client: FakeClient):
        tried.append(client.key)
        if client.key == "bad-key":
            raise RuntimeError("API_KEY_INVALID: API key not valid")
        return "ok"

    assert service._with_retry(operation) == "ok"
    assert tried == ["bad-key", "good-key"]


def test_deadline_error_gets_a_retry(monkeypatch):
    service = GeminiService(api_keys=["good-key"], request_timeout_sec=1)
    calls = 0
    monkeypatch.setattr(service, "_client_for_key", lambda _key: object())
    # Avoid a real cooldown wait while still exercising the retry decision.
    monkeypatch.setattr(service.key_pool, "report_failure", lambda _slot, _error: None)

    def operation(_client):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("504 DEADLINE_EXCEEDED")
        return {"status": "ok"}

    assert service._with_retry(operation) == {"status": "ok"}
    assert calls == 2


def test_single_attempt_waits_for_short_key_cooldown_then_calls(monkeypatch):
    from app.key_pool import KeyUnavailableError

    service = GeminiService(api_keys=["good-key"], request_timeout_sec=1)
    slot = service.key_pool._slots[0]
    acquire_calls = 0
    sleeps: list[float] = []
    monkeypatch.setattr(service.key_pool, "acquire", lambda: _acquire_once_then_slot())

    def _acquire_once_then_slot():
        nonlocal acquire_calls
        acquire_calls += 1
        if acquire_calls == 1:
            raise KeyUnavailableError("brief cooldown")
        return slot

    monkeypatch.setattr(service.key_pool, "next_available_in_seconds", lambda: 0.2)
    monkeypatch.setattr("app.gemini_client.time.sleep", sleeps.append)
    monkeypatch.setattr(service, "_client_for_key", lambda _key: object())

    assert service._with_retry(lambda _client: "ok", max_attempts=1) == "ok"
    assert acquire_calls == 2
    assert sleeps == [pytest.approx(0.3)]


def test_vision_rate_limit_tries_next_flash_model(monkeypatch):
    service = GeminiService(api_keys=["good-key"], request_timeout_sec=1)
    tried: list[str] = []
    monkeypatch.setattr(service, "_vision_candidates", lambda: ["gemini-3.8-flash", "gemini-3.6-flash"])

    def generate(*, model, **_kwargs):
        tried.append(model)
        if model == "gemini-3.8-flash":
            raise RuntimeError("429 RESOURCE_EXHAUSTED rate limit")
        return {"summary": "review complete"}

    monkeypatch.setattr(service, "_generate_json_impl", generate)
    result = service.generate_json(
        model="gemma-4-26b-a4b-it",
        image_parts=[(b"image", "image/png")],
        prompt="inspect",
        response_schema={"type": "object"},
        temperature=0,
        max_output_tokens=100,
    )

    assert result["summary"] == "review complete"
    assert tried == ["gemini-3.8-flash", "gemini-3.6-flash"]


def test_rate_limit_is_reported_instead_of_mislabeled_as_json(monkeypatch):
    service = GeminiService(api_keys=["good-key"], request_timeout_sec=1)

    def rate_limited(_operation):
        raise RuntimeError("Gemini API rate limit reached")

    monkeypatch.setattr(service, "_with_retry", rate_limited)
    with pytest.raises(RuntimeError, match="Photo PCB Inspector stopped: Gemini API rate limit"):
        service.generate_json(
            model="gemma-4-26b-a4b-it",
            prompt="Return an empty report.",
            response_schema={"type": "object"},
            temperature=0,
            max_output_tokens=128,
            task_name="Photo PCB Inspector",
        )
