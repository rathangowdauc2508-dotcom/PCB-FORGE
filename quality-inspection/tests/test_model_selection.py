from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.gemini_client import GeminiService
from app.orchestrator import OrchestrationEngine
from app.schemas import ModelInfo


class _FakeGeminiService:
    def __init__(self, model_names: list[str]):
        self.model_names = model_names

    def list_generate_models(self):
        return [ModelInfo(name=name) for name in self.model_names]

    def pick_recommended_model(self, available, default_model=None):  # pragma: no cover - passthrough helper
        return GeminiService.pick_recommended_model(available, default_model=default_model)

    @staticmethod
    def resolve_model_name(name: str | None) -> str | None:
        return GeminiService.resolve_model_name(name)


class _BrokenGeminiService(_FakeGeminiService):
    def list_generate_models(self):
        raise RuntimeError("gemini unavailable")


def _mk_settings(tmp_path: Path, *, default_model: str | None) -> Settings:
    background = tmp_path / "background.md"
    todo = tmp_path / "todo.md"
    example = tmp_path / "example.md"
    for p in (background, todo, example):
        p.write_text("ctx", encoding="utf-8")

    return Settings(
        gemini_api_key=None,
        gemini_api_keys=["key"],
        default_model=default_model,
        default_temperature=0.2,
        max_output_tokens=1024,
        request_timeout_sec=30,
        context_background_path=background,
        context_todo_path=todo,
        context_example_path=example,
        demo_case_path=tmp_path / "demo_case.json",
    )


def test_resolve_gemma4_alias_to_supported_26b_model():
    assert GeminiService.resolve_model_name("gemma-4") == "gemma-4-26b-a4b-it"


def test_resolve_model_keeps_explicit_26b_selection():
    assert GeminiService.resolve_model_name("gemma-4-26b-a4b-it") == "gemma-4-26b-a4b-it"


def test_pick_recommended_model_prefers_default_flash_alias(tmp_path):
    fake = _FakeGeminiService(["gemma-4-31b-it", "gemma-4-26b-a4b-it"])
    available = fake.list_generate_models()
    assert (
        GeminiService.pick_recommended_model(
            available,
            default_model="gemma-4",
        )
        == "gemma-4-26b-a4b-it"
    )


def test_orchestrator_accepts_flash_alias_as_request(tmp_path):
    fake = _FakeGeminiService(["gemma-4-31b-it", "gemma-4-26b-a4b-it"])
    engine = OrchestrationEngine(
        settings=_mk_settings(tmp_path, default_model=None),
        gemini_service=fake,
    )
    model = engine._pick_model("gemma-4")
    assert model == "gemma-4-26b-a4b-it"


def test_orchestrator_fallback_resolves_default_alias_when_list_fails(tmp_path):
    broken = _BrokenGeminiService([])
    engine = OrchestrationEngine(
        settings=_mk_settings(tmp_path, default_model="gemma-4"),
        gemini_service=broken,
    )
    model = engine._pick_model(None)
    assert model == "gemma-4-26b-a4b-it"


def test_orchestrator_uses_gemini_flash_as_default_when_available(tmp_path):
    fake = _FakeGeminiService(["gemma-4-26b-a4b-it", "gemini-3.8-flash"])
    engine = OrchestrationEngine(
        settings=_mk_settings(tmp_path, default_model="gemini-3.8-flash"),
        gemini_service=fake,
    )
    assert engine._pick_model(None) == "gemini-3.8-flash"
