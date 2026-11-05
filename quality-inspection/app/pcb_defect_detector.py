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
MODEL_CLASS_NAMES = {
    0: "BMFO",
    1: "CFO",
    2: "CS",
    3: "HB",
    4: "MB",
    5: "OP",
    6: "SC",
    7: "SH",
    8: "SP",
}
CLASS_CONFIDENCE_THRESHOLDS = {
    0: 0.37,
    1: 0.31,
    2: 0.29,
    3: 0.75,
    4: 0.22,
    5: 0.40,
    6: 0.39,
    7: 0.56,
    8: 0.38,
}
MIN_CONFIDENCE_THRESHOLD = min(CLASS_CONFIDENCE_THRESHOLDS.values())


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
        "detector": "YOLOv8 PCB defect detector (9 classes)" if mode == "yolo" else "Gemma 4 photo review (compatibility mode)",
        "mode": mode,
        "ready": weights_ready or gemma_ready,
        "gemma_fallback_available": gemma_ready,
        "ultralytics_installed": package_available,
        "weights_found": path.is_file(),
        "weights_path": str(path),
        "class_count": len(MODEL_CLASS_NAMES),
        "required_classes": list(MODEL_CLASS_NAMES.values()),
        "confidence_thresholds": {
            MODEL_CLASS_NAMES[class_id]: threshold
            for class_id, threshold in CLASS_CONFIDENCE_THRESHOLDS.items()
        },
    }


@lru_cache(maxsize=1)
def _load_model(path: str):
    from ultralytics import YOLO
    return YOLO(path)


def _class_names_by_id(names: Any) -> dict[int, str]:
    try:
        if isinstance(names, dict):
            return {int(class_id): str(name) for class_id, name in names.items()}
        return {class_id: str(name) for class_id, name in enumerate(names)}
    except (TypeError, ValueError) as exc:
        raise DetectorModelError("The selected weights contain invalid class metadata.") from exc


def _validate_model_classes(names: Any) -> dict[int, str]:
    actual = _class_names_by_id(names)
    if actual != MODEL_CLASS_NAMES:
        raise DetectorModelError(
            "The selected weights do not match PCB Forge's nine-class PCB defect model. "
            f"Expected ID ordering: {MODEL_CLASS_NAMES}; actual ID ordering: {actual}."
        )
    return actual


def _plot_filtered_result(result: Any, kept_indices: list[int]) -> np.ndarray:
    """Render only detections that survived the per-class confidence filters."""
    original_boxes = result.boxes
    if original_boxes is None or len(kept_indices) == len(original_boxes):
        return result.plot()

    result.boxes = original_boxes[kept_indices]
    try:
        return result.plot()
    finally:
        result.boxes = original_boxes


def detect_pcb_defects(
    image_bytes: bytes,
    *,
    confidence_threshold: float | None = None,
) -> dict[str, Any]:
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
    class_names = _validate_model_classes(model.names)
    if confidence_threshold is not None and not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("Confidence threshold must be between 0 and 1.")
    # Preserve the legacy keyword argument without allowing it to discard a class
    # before that class's optimized threshold is applied below.
    inference_confidence = (
        min(float(confidence_threshold), MIN_CONFIDENCE_THRESHOLD)
        if confidence_threshold is not None
        else MIN_CONFIDENCE_THRESHOLD
    )
    # Ultralytics treats numpy inputs as OpenCV-style BGR images.
    source = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])
    started = time.perf_counter()
    result = model.predict(source=source, conf=inference_confidence, imgsz=640, device="cpu", verbose=False)[0]
    inference_ms = round((time.perf_counter() - started) * 1000)
    boxes = result.boxes
    detections: list[dict[str, Any]] = []
    kept_indices: list[int] = []
    if boxes is not None and len(boxes):
        xyxy = boxes.xyxy.cpu().tolist()
        classes = boxes.cls.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        for raw_index, (coords, class_id_value, confidence_value) in enumerate(zip(xyxy, classes, confidences)):
            class_id = int(class_id_value)
            if class_id not in class_names:
                raise DetectorModelError(f"The model returned an unknown class ID: {class_id}.")
            confidence = float(confidence_value)
            if confidence < CLASS_CONFIDENCE_THRESHOLDS[class_id]:
                continue
            kept_indices.append(raw_index)
            detections.append({
                "id": len(detections) + 1,
                "class_name": class_names[class_id],
                "confidence": round(confidence, 4),
                "bbox": {
                    "x1": round(float(coords[0]), 1), "y1": round(float(coords[1]), 1),
                    "x2": round(float(coords[2]), 1), "y2": round(float(coords[3]), 1),
                },
            })

    # Ultralytics plot() returns a BGR numpy image. Convert before JPEG encoding.
    annotated_bgr = _plot_filtered_result(result, kept_indices)
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
