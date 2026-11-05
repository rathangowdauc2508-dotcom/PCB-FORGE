"""PCB defect analysis routes (ported from pcb-analysis/backend/src/routes/analysis.py)."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..analyzer import analyze_test_image, load_template, save_template, template_exists
from ..gemma_photo_inspect import inspect_photo_with_gemma
from ..image_utils import image_to_base64
from ..pcb_defect_detector import DetectorModelError, detect_pcb_defects, detector_status
from ..schemas import ImageInput
from ..utils import load_image_bytes

router = APIRouter(prefix="/analysis", tags=["analysis"])


class PCBDetectionRequest(BaseModel):
    image: ImageInput
    engine: Literal["auto", "trained", "gemini"] = "auto"


def _gemma_available() -> bool:
    return getattr(__import__("app.main", fromlist=["app"]).app.state, "engine", None) is not None


@router.get("/detector-status")
def get_pcb_detector_status() -> dict:
    status = detector_status()
    status["yolo_ready"] = bool(status["ultralytics_installed"] and status["weights_found"])
    status["gemini_available"] = _gemma_available()
    status["ready"] = bool(status["yolo_ready"] or status["gemini_available"])
    status["backend"] = "yolo" if status["yolo_ready"] else ("gemini" if status["gemini_available"] else "none")
    return status


@router.post("/detect-defects")
def detect_uploaded_pcb(payload: PCBDetectionRequest) -> dict:
    image_bytes = load_image_bytes(payload.image, Path(__file__).resolve().parents[1])
    status = detector_status()
    yolo_ready = bool(status["ultralytics_installed"] and status["weights_found"])
    if payload.engine == "trained" and not yolo_ready:
        raise HTTPException(
            status_code=503,
            detail="The trained PCB detector is not ready. Install Ultralytics and set PCB_DEFECT_MODEL_PATH to your trained .pt weights.",
        )
    use_gemini = payload.engine == "gemini" or (payload.engine == "auto" and not yolo_ready)
    if use_gemini:
        engine = _get_engine()  # 503 with a clear message if no Gemini key
        try:
            model = engine._pick_model(None)
            return inspect_photo_with_gemma(engine.gemini, model, image_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Photo inspection failed: {exc}") from exc
    try:
        return detect_pcb_defects(image_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DetectorModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="YOLOv8 is not installed in the inspection environment. Install quality-inspection/requirements-yolo.txt, then restart the inspection API.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YOLOv8 inspection failed: {exc}") from exc


def _get_engine():
    from ..main import get_engine
    return get_engine()


@router.post("/template")
async def upload_template(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    save_template(image_bytes)
    return {"status": "ok", "message": "Template uploaded successfully"}


@router.get("/template")
async def get_template_status():
    if not template_exists():
        return {"exists": False, "image": None}

    template_bytes = load_template()
    return {"exists": True, "image": image_to_base64(template_bytes)}


@router.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    if not template_exists():
        raise HTTPException(status_code=400, detail="No template uploaded. Upload a template first.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    engine = _get_engine()

    try:
        result = await analyze_test_image(image_bytes, gemini_service=engine.gemini)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result.model_dump()
