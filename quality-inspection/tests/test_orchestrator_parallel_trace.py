from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.orchestrator import OrchestrationEngine
from app.schemas import ImageInput, ModelInfo, OrchestrationInput, OrchestrationOptions, OrchestrationRequest


class _FakeGemini:
    def list_generate_models(self):
        return [ModelInfo(name="gemma-4-26b-a4b-it")]

    @staticmethod
    def pick_recommended_model(available, default_model=None):
        _ = available, default_model
        return "gemma-4-26b-a4b-it"


class _StubRunner:
    def __init__(self, **kwargs):
        _ = kwargs

    def run_symptom_agent(
        self,
        error_log: str,
        spec_focus_plan: str | None = None,
        spec_image_parts: list[tuple[bytes, str]] | None = None,
    ):
        _ = error_log, spec_focus_plan, spec_image_parts
        return {
            "error_interpretation": "short risk",
            "suspect_parts": [
                {
                    "part_name": "U2",
                    "likely_fault_mode": "bridge",
                    "why_related": "adjacent nets",
                    "confidence": 0.8,
                }
            ],
            "handoff_message": "symptom->parallel",
        }

    def run_spec_precheck_agent(self, spec_excerpt: str, symptom_result: dict):
        _ = spec_excerpt, symptom_result
        return {
            "spec_watchlist": [
                {
                    "rule_id": "SPACING-SHORT-001",
                    "what_to_check": "net spacing",
                    "why_relevant": "short risk",
                    "priority": "high",
                }
            ],
            "spec_risk_summary": "Check adjacent net spacing and bridge residue.",
            "handoff_message": "spec->physical",
        }

    def run_design_agent(
        self,
        symptom_result: dict,
        heuristic_bbox: dict | None,
        design_reference_text: str | None,
        design_image: tuple[bytes, str],
    ):
        _ = symptom_result, heuristic_bbox, design_reference_text, design_image
        return {
            "cad_mappings": [
                {
                    "part_name": "U2",
                    "schematic_reference": "Sheet1/U2",
                    "reason": "error linked region",
                    "bbox": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                }
            ],
            "handoff_message": "design->physical",
        }

    def run_physical_agent(
        self,
        symptom_result: dict,
        spec_precheck_result: dict,
        design_result: dict,
        heuristic_bbox: dict | None,
        tested_image: tuple[bytes, str],
    ):
        _ = symptom_result, spec_precheck_result, design_result, heuristic_bbox, tested_image
        return {
            "defect_verification": [
                {
                    "part_name": "U2",
                    "defect_type": "short",
                    "evidence": "bridge exists",
                    "crop_note": "zoomed region",
                    "confidence": 0.9,
                    "bbox": {"x1": 11, "y1": 21, "x2": 31, "y2": 41},
                }
            ],
            "root_cause_candidate": "bridge residue",
            "impact": "bus error",
            "handoff_message": "physical->spec-final",
        }

    def run_spec_final_agent(
        self,
        spec_excerpt: str,
        symptom_result: dict,
        spec_precheck_result: dict,
        design_result: dict,
        physical_result: dict,
    ):
        _ = spec_excerpt, symptom_result, spec_precheck_result, design_result, physical_result
        return {
            "spec_checks": [
                {
                    "rule_id": "SPACING-SHORT-001",
                    "rule_text": "keep spacing",
                    "compliance_status": "fail",
                    "gap": "bridge found",
                }
            ],
            "final_root_cause": "etch residue caused short",
            "final_resolution": ["clean and rework", "continuity retest"],
            "final_confidence": 0.88,
        }


def test_orchestrator_parallel_trace(monkeypatch, tmp_path: Path):
    from app.diff_engine import DiffBoundingBox, DiffRegion

    monkeypatch.setattr("app.orchestrator.AgentRunner", _StubRunner)
    monkeypatch.setattr("app.orchestrator.load_image_bytes", lambda _image, _root: b"img")
    monkeypatch.setattr(
        "app.orchestrator.compute_diff",
        lambda _a, _b: [
            DiffRegion(
                bounding_box=DiffBoundingBox(x_min=1, y_min=2, x_max=3, y_max=4),
                crop_raw=b"raw",
                crop_highlighted=b"highlighted",
                area=100,
            )
        ],
    )
    monkeypatch.setattr("app.orchestrator.resolve_spec_excerpt", lambda **_kwargs: "spec excerpt")

    background = tmp_path / "background.md"
    todo = tmp_path / "todo.md"
    example = tmp_path / "example.md"
    for p in (background, todo, example):
        p.write_text("ctx", encoding="utf-8")

    settings = Settings(
        gemini_api_key=None,
        gemini_api_keys=["AIzaSy_dummy_valid_key_1234567890"],
        default_model=None,
        default_temperature=0.2,
        max_output_tokens=1200,
        request_timeout_sec=60,
        context_background_path=background,
        context_todo_path=todo,
        context_example_path=example,
        demo_case_path=tmp_path / "demo_case.json",
    )
    engine = OrchestrationEngine(settings=settings, gemini_service=_FakeGemini())

    request = OrchestrationRequest(
        input=OrchestrationInput(
            error_log="[ERROR] NET_SHORT_DETECTED",
            spec_excerpt="rule text",
            design_image=ImageInput(mime_type="image/png", file_path="design.png"),
            tested_image=ImageInput(mime_type="image/png", file_path="tested.png"),
        ),
        options=OrchestrationOptions(include_raw_agent_payloads=False),
    )

    response = engine.run(request)

    assert [t.agent_id for t in response.agent_trace] == ["agent_1", "agent_2a", "agent_2b", "agent_3", "agent_4"]
    assert response.agent_trace[0].handoff_to == "agent_2a,agent_2b"
    assert response.output.root_cause == "etch residue caused short"
    assert response.output.bounding_boxes[0].label == "short"
