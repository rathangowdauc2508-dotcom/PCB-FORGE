from pathlib import Path

import pytest

from app.config import Settings
from app.gemini_client import GeneratedJSON
from app.orchestrator import OrchestrationEngine
from app.schemas import (
    ImageInput,
    ModelInfo,
    OrchestrationInput,
    OrchestrationOptions,
    OrchestrationRequest,
)


class FakeGemini:
    def __init__(self, fallback_fails=False, timeout_gemini_primary=False, rate_limited_gemini_primary=False):
        self.calls = []
        self.failed_primary = False
        self.fallback_fails = fallback_fails
        self.timeout_gemini_primary = timeout_gemini_primary
        self.rate_limited_gemini_primary = rate_limited_gemini_primary

    def list_generate_models(self):
        return [ModelInfo(name="gemma-4-26b-a4b-it"), ModelInfo(name="gemini-3.8-flash")]

    @staticmethod
    def resolve_model_name(name):
        return name

    @staticmethod
    def pick_recommended_model(_available, default_model=None):
        return default_model or "gemma-4-26b-a4b-it"

    def generate_json(self, *, task_name, model, image_parts=None, **_kwargs):
        self.calls.append((task_name, model))
        if task_name == "Error Analyzer" and model.startswith("gemma") and not self.failed_primary:
            self.failed_primary = True
            raise RuntimeError("504 DEADLINE_EXCEEDED")
        if task_name == "Error Analyzer" and model == "gemini-3.8-flash" and self.timeout_gemini_primary and not self.failed_primary:
            self.failed_primary = True
            raise RuntimeError("504 DEADLINE_EXCEEDED")
        if task_name == "Error Analyzer" and model == "gemini-3.8-flash" and self.rate_limited_gemini_primary and not self.failed_primary:
            self.failed_primary = True
            raise RuntimeError("429 RESOURCE_EXHAUSTED rate limit")
        if model.startswith("gemini-") and self.fallback_fails:
            raise RuntimeError("503 SERVICE UNAVAILABLE")
        # The production service uses Gemini Flash for image input; preserve that
        # distinction in the mocked agent traces too.
        actual = "gemini-3.8-flash" if image_parts else model
        return GeneratedJSON({}, actual)


def _engine(monkeypatch, tmp_path: Path, gemini: FakeGemini, default_model="gemma-4-26b-a4b-it"):
    for name in ("background.md", "todo.md", "example.md"):
        (tmp_path / name).write_text("test context", encoding="utf-8")
    settings = Settings(
        gemini_api_key=None,
        gemini_api_keys=["AIzaSy_dummy_valid_key_1234567890"],
        default_model=default_model,
        default_temperature=0.1,
        max_output_tokens=768,
        request_timeout_sec=8,
        context_background_path=tmp_path / "background.md",
        context_todo_path=tmp_path / "todo.md",
        context_example_path=tmp_path / "example.md",
        demo_case_path=tmp_path / "demo.json",
    )
    monkeypatch.setattr("app.orchestrator.load_image_bytes", lambda *_args: b"fake image")
    monkeypatch.setattr("app.orchestrator.compute_diff", lambda *_args: [])
    monkeypatch.setattr("app.orchestrator.resolve_spec_excerpt", lambda **_kwargs: "sample spec")
    return OrchestrationEngine(settings=settings, gemini_service=gemini)


def _request(model="gemma-4-26b-a4b-it"):
    return OrchestrationRequest(
        input=OrchestrationInput(
            error_log="test symptom",
            spec_excerpt="sample spec",
            design_image=ImageInput(mime_type="image/png", file_path="design.png"),
            tested_image=ImageInput(mime_type="image/png", file_path="tested.png"),
        ),
        options=OrchestrationOptions(model=model),
    )


def test_timeout_switches_remaining_agents_once_and_returns_full_trace(monkeypatch, tmp_path):
    gemini = FakeGemini()
    engine = _engine(monkeypatch, tmp_path, gemini)
    progress = []

    result = engine.run(_request(), progress=progress.append)

    assert [trace.agent_id for trace in result.agent_trace] == ["agent_1", "agent_2a", "agent_2b", "agent_3", "agent_4"]
    assert [name for name, _model in gemini.calls].count("Error Analyzer") == 2
    assert all(trace.model_used == "gemini-3.8-flash" for trace in result.agent_trace)
    assert result.model_used.startswith("gemma-4-26b-a4b-it (primary)")
    assert "fallback" in progress


def test_normal_run_keeps_gemma_for_text_agents(monkeypatch, tmp_path):
    gemini = FakeGemini()
    # Avoid the simulated initial timeout on this path.
    gemini.failed_primary = True
    engine = _engine(monkeypatch, tmp_path, gemini)

    result = engine.run(_request())

    assert result.agent_trace[0].model_used == "gemma-4-26b-a4b-it"
    assert result.agent_trace[1].model_used == "gemma-4-26b-a4b-it"
    assert result.agent_trace[2].model_used == "gemini-3.8-flash"
    assert "primary" in result.model_used


def test_default_run_uses_gemini_flash_as_primary(monkeypatch, tmp_path):
    gemini = FakeGemini()
    engine = _engine(monkeypatch, tmp_path, gemini, default_model="gemini-3.8-flash")

    result = engine.run(_request(model="gemini-3.8-flash"))

    assert all(trace.model_used == "gemini-3.8-flash" for trace in result.agent_trace)
    assert result.model_used.startswith("gemini-3.8-flash (primary)")


def test_gemini_timeout_switches_to_distinct_flash_model(monkeypatch, tmp_path):
    gemini = FakeGemini(timeout_gemini_primary=True)
    engine = _engine(monkeypatch, tmp_path, gemini, default_model="gemini-3.8-flash")

    result = engine.run(_request(model="gemini-3.8-flash"))

    analyzer_models = [model for name, model in gemini.calls if name == "Error Analyzer"]
    assert analyzer_models == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert result.agent_trace[0].model_used == "gemini-3.6-flash"


def test_gemini_rate_limit_tries_distinct_flash_model(monkeypatch, tmp_path):
    gemini = FakeGemini(rate_limited_gemini_primary=True)
    engine = _engine(monkeypatch, tmp_path, gemini, default_model="gemini-3.8-flash")

    result = engine.run(_request(model="gemini-3.8-flash"))

    analyzer_models = [model for name, model in gemini.calls if name == "Error Analyzer"]
    assert analyzer_models == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert result.agent_trace[0].model_used == "gemini-3.6-flash"


def test_fallback_failure_is_returned_without_restarting_pipeline(monkeypatch, tmp_path):
    gemini = FakeGemini(fallback_fails=True)
    engine = _engine(monkeypatch, tmp_path, gemini)

    with pytest.raises(RuntimeError, match="503 SERVICE UNAVAILABLE"):
        engine.run(_request())

    assert [name for name, _model in gemini.calls].count("Error Analyzer") == 4
    assert len(gemini.calls) == 4
