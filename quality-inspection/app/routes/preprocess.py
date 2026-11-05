from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..demo_data import load_demo_case
from ..file_processing import ErrorCodeGenerateInput, SpecResolveInput, VisionDiffInput, VisionProbeOptions
from ..schemas import VisionProbeResponse
from ..spec_parser import resolve_spec_excerpt
from ..utils import load_image_bytes
from ..vision_diff import detect_diff_bbox

router = APIRouter(tags=["preprocess"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_engine():
    from ..main import get_engine
    return get_engine()


@router.post("/models/vision/probe", response_model=VisionProbeResponse)
def probe_vision_models(options: VisionProbeOptions | None = None) -> VisionProbeResponse:
    engine = _get_engine()
    options = options or VisionProbeOptions()

    try:
        available = engine.list_models()
        default_candidates = [
            model.name
            for model in available
            if model.name.startswith("gemma-4")
        ]
        candidate_models = options.candidate_models or sorted(set(default_candidates))

        image_path = Path(options.image_path or "data/assets/tested_board.png")
        if not image_path.is_absolute():
            image_path = (_PROJECT_ROOT / image_path).resolve()
        image_bytes = image_path.read_bytes()

        results = engine.gemini.probe_vision_models(
            candidate_models=candidate_models,
            image_bytes=image_bytes,
            mime_type="image/png",
        )
        return VisionProbeResponse(
            probed_at=datetime.now(tz=UTC),
            candidate_models=candidate_models,
            results=results,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vision probe failed: {exc}") from exc


@router.post("/preprocess/error-code/generate")
def preprocess_generate_error_code(payload: ErrorCodeGenerateInput) -> dict:
    engine = _get_engine()
    try:
        model = engine._pick_model(payload.model)
        schema = {
            "type": "object",
            "properties": {
                "error_log": {"type": "string"},
                "error_code": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["error_log", "error_code", "explanation"],
        }
        prompt = (
            "Generate one realistic hardware validation error log for a hackathon demo.\n"
            f"interface: {payload.interface}\n"
            f"symptom: {payload.symptom}\n"
            f"context: {payload.context or 'PCB manufacturing validation'}\n"
            "Return concise output."
        )
        generated = engine.gemini.generate_json(
            model=model,
            prompt=prompt,
            response_schema=schema,
            temperature=0.2,
            max_output_tokens=220,
        )
        return {"model_used": model, "generated": generated}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error-code generation failed: {exc}") from exc


@router.post("/preprocess/spec/resolve")
def preprocess_spec_resolve(payload: SpecResolveInput) -> dict:
    try:
        resolved = resolve_spec_excerpt(
            spec_excerpt=payload.spec_excerpt,
            spec_document_path=payload.spec_document_path,
            error_log=payload.error_log,
            root_dir=_PROJECT_ROOT,
        )
        return {
            "resolved_spec_excerpt": resolved,
            "source": "spec_excerpt" if payload.spec_excerpt else payload.spec_document_path,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Spec resolve failed: {exc}") from exc


@router.post("/preprocess/vision/diff-box")
def preprocess_vision_diff(payload: VisionDiffInput) -> dict:
    try:
        design_bytes = load_image_bytes(payload.design_image, _PROJECT_ROOT)
        tested_bytes = load_image_bytes(payload.tested_image, _PROJECT_ROOT)
        bbox = detect_diff_bbox(design_bytes, tested_bytes)
        return {"heuristic_diff_bbox": bbox}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Vision diff failed: {exc}") from exc


@router.get("/demo-case")
def demo_case():
    settings = get_settings()
    return load_demo_case(settings)
