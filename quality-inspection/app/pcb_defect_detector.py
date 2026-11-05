"""YOLOv8 PCB defect inference, adapted for PCB Forge's FastAPI inspection UI."""
from __future__ import annotations

import base64
import importlib.util
import io
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .config import get_settings


QUALITY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = QUALITY_ROOT / "models" / "best.pt"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
EXPECTED_CLASSES = {
    "missinghole", "mousebite", "opencircuit", "short", "spur", "spuriouscopper",
}


class DetectorModelError(RuntimeError):
    """The supplied weights do not match PCB Forge's expected defect classes."""


def model_path() -> Path:
    configured = os.getenv("PCB_DEFECT_MODEL_PATH", "").strip()
    path = Path(configured).expanduser() if configured else DEFAULT_WEIGHTS
    if not path.is_absolute():
        path = QUALITY_ROOT / path
    return path.resolve()


def detector_status() -> dict[str, Any]:
    path = model_path()
    # Avoid importing torch/ultralytics just to paint the page's readiness badge.
    package_available = importlib.util.find_spec("ultralytics") is not None
    weights_ready = package_available and path.is_file()
    gemma_ready = bool(get_settings().gemini_api_keys)
    mode = "yolo" if weights_ready or not gemma_ready else "legacy-gemma"
    return {
        "detector": "YOLOv8 PCB defect detector" if mode == "yolo" else "Gemma 4 photo review (compatibility mode)",
        "mode": mode,
        "ready": weights_ready or gemma_ready,
        "gemma_fallback_available": gemma_ready,
        "ultralytics_installed": package_available,
        "weights_found": path.is_file(),
        "weights_path": str(path),
        "required_classes": [
            "missing_hole", "mouse_bite", "open_circuit", "short", "spur", "spurious_copper",
        ],
    }


@lru_cache(maxsize=1)
def _load_model(path: str):
    from ultralytics import YOLO
    return YOLO(path)


def _validate_model_classes(names: Any) -> None:
    values = names.values() if isinstance(names, dict) else names
    normalized = {"".join(char for char in str(name).lower() if char.isalnum()) for name in values}
    if normalized != EXPECTED_CLASSES:
        missing = sorted(EXPECTED_CLASSES - normalized)
        extra = sorted(normalized - EXPECTED_CLASSES)
        raise DetectorModelError(
            "The selected weights do not match PCB Forge's six-class PCB defect model. "
            f"Missing classes: {missing or 'none'}; unexpected classes: {extra or 'none'}."
        )


def detect_pcb_defects(image_bytes: bytes, *, confidence_threshold: float = 0.25) -> dict[str, Any]:
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image is too large. Maximum upload size is 20 MB.")

    path = model_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"PCB defect weights are missing: {path}. Put the trained best.pt file there "
            "or set PCB_DEFECT_MODEL_PATH to its location."
        )
    try:
        opened = Image.open(io.BytesIO(image_bytes))
        if opened.width * opened.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions are too large to inspect safely.")
        image = opened.convert("RGB")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this image. Upload a valid PNG, JPG, or WEBP board photo.") from exc

    model = _load_model(str(path))
    _validate_model_classes(model.names)
    source = np.asarray(image)
    started = time.perf_counter()
    result = model.predict(source=source, conf=confidence_threshold, imgsz=640, device="cpu", verbose=False)[0]
    inference_ms = round((time.perf_counter() - started) * 1000)
    names = result.names
    boxes = result.boxes
    detections: list[dict[str, Any]] = []
    if boxes is not None and len(boxes):
        xyxy = boxes.xyxy.cpu().tolist()
        classes = boxes.cls.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        for index, (coords, class_id, confidence) in enumerate(zip(xyxy, classes, confidences), start=1):
            name = names.get(int(class_id), str(int(class_id))) if isinstance(names, dict) else names[int(class_id)]
            detections.append({
                "id": index,
                "class_name": str(name),
                "confidence": round(float(confidence), 4),
                "bbox": {
                    "x1": round(float(coords[0]), 1), "y1": round(float(coords[1]), 1),
                    "x2": round(float(coords[2]), 1), "y2": round(float(coords[3]), 1),
                },
            })

    # Ultralytics plot() returns a BGR numpy image. Convert before JPEG encoding.
    annotated_bgr = result.plot()
    annotated_rgb = Image.fromarray(annotated_bgr[:, :, ::-1])
    output = io.BytesIO()
    annotated_rgb.save(output, format="JPEG", quality=88, optimize=True)
    return {
        "model_name": "YOLOv8 PCB defect detector",
        "model_weights": path.name,
        "image_width": image.width,
        "image_height": image.height,
        "inference_ms": inference_ms,
        "detections": detections,
        "annotated_image_base64": base64.b64encode(output.getvalue()).decode("ascii"),
    }
