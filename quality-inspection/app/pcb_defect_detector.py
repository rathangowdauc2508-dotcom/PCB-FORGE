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
from PIL import ImageDraw, ImageFont

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


def _annotation_font(image_width: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(12, min(24, round(image_width / 75)))
    for path in (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label_rect(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    box: dict[str, float],
    image_width: int,
    image_height: int,
    occupied: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float] | None:
    text_box = draw.textbbox((0, 0), text, font=font)
    label_width = text_box[2] - text_box[0] + 10
    label_height = text_box[3] - text_box[1] + 6
    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
    gap = 4
    candidates = [
        (x1, y1 - label_height - gap),
        (x1, y2 + gap),
        (x2 - label_width, y1 - label_height - gap),
        (x2 - label_width, y2 + gap),
        (x2 + gap, y1),
        (x1 - label_width - gap, y1),
    ]

    def clamp(candidate: tuple[float, float]) -> tuple[float, float]:
        return (
            min(max(0, candidate[0]), max(0, image_width - label_width)),
            min(max(0, candidate[1]), max(0, image_height - label_height)),
        )

    def overlaps(candidate: tuple[float, float]) -> bool:
        left, top = candidate
        right, bottom = left + label_width, top + label_height
        return any(
            left < other_right and right > other_left
            and top < other_bottom and bottom > other_top
            for other_left, other_top, other_right, other_bottom in occupied
        )

    search_candidates = candidates[:]
    step_x = max(label_width + gap, image_width / 18)
    step_y = max(label_height + gap, image_height / 18)
    for radius in range(1, 13):
        for column, row in (
            (0, -radius), (1, -radius), (-1, -radius),
            (radius, 0), (radius, 1), (radius, -1),
            (0, radius), (1, radius), (-1, radius),
            (-radius, 0), (-radius, 1), (-radius, -1),
        ):
            search_candidates.append((x1 + column * step_x, y1 + row * step_y))

    for candidate in search_candidates:
        position = clamp(candidate)
        if not overlaps(position):
            rect = (*position, position[0] + label_width, position[1] + label_height)
            occupied.append(rect)
            return rect

    return None


def _marker_rect(
    box: dict[str, float],
    marker_size: int,
    image_width: int,
    image_height: int,
    occupied: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
    gap = 3
    candidates = [
        (x1, y1 - marker_size - gap), (x1, y2 + gap),
        (x2 - marker_size, y1 - marker_size - gap), (x2 - marker_size, y2 + gap),
        (x2 + gap, y1), (x1 - marker_size - gap, y1),
    ]

    def clamp(candidate: tuple[float, float]) -> tuple[float, float]:
        return (
            min(max(0, candidate[0]), max(0, image_width - marker_size)),
            min(max(0, candidate[1]), max(0, image_height - marker_size)),
        )

    def overlaps(candidate: tuple[float, float]) -> bool:
        left, top = candidate
        right, bottom = left + marker_size, top + marker_size
        return any(
            left < other_right and right > other_left
            and top < other_bottom and bottom > other_top
            for other_left, other_top, other_right, other_bottom in occupied
        )

    for candidate in candidates:
        position = clamp(candidate)
        if not overlaps(position):
            rect = (*position, position[0] + marker_size, position[1] + marker_size)
            occupied.append(rect)
            return rect

    position = clamp((x1, y1))
    rect = (*position, position[0] + marker_size, position[1] + marker_size)
    occupied.append(rect)
    return rect


def _draw_annotations(
    image: Image.Image,
    detections: list[dict[str, Any]],
) -> Image.Image:
    draw = ImageDraw.Draw(image, "RGBA")
    font = _annotation_font(image.width)
    occupied: list[tuple[float, float, float, float]] = []
    palette = (
        (220, 72, 84), (230, 126, 48), (51, 142, 235),
        (154, 91, 214), (32, 157, 111), (201, 87, 145),
        (39, 161, 170), (236, 177, 52), (104, 111, 218),
    )
    marker_size = max(18, min(30, round(image.width / 45)))
    fallback_entries: list[tuple[int, dict[str, Any]]] = []

    for index, detection in enumerate(detections):
        box = detection["bbox"]
        color = palette[index % len(palette)]
        draw.rectangle(
            [box["x1"], box["y1"], box["x2"], box["y2"]],
            outline=(*color, 255),
            width=max(2, round(image.width / 500)),
        )
        text = f'{detection["class_name"]} {detection["confidence"]:.0%}'
        label_rect = _label_rect(
            draw, text, font, box, image.width, image.height, occupied,
        )
        if label_rect is not None:
            left, top, right, bottom = label_rect
            draw.rounded_rectangle(
                [left, top, right, bottom],
                radius=3,
                fill=(*color, 235),
                outline=(255, 255, 255, 210),
                width=1,
            )
            draw.text((left + 5, top + 3), text, fill=(255, 255, 255, 255), font=font)
            continue

        marker_rect = _marker_rect(
            box, marker_size, image.width, image.height, occupied,
        )
        left, top, right, bottom = marker_rect
        draw.ellipse(
            marker_rect,
            fill=(*color, 245),
            outline=(255, 255, 255, 230),
            width=1,
        )
        marker = str(index + 1)
        marker_box = draw.textbbox((0, 0), marker, font=font)
        draw.text(
            (left + (right - left - (marker_box[2] - marker_box[0])) / 2,
             top + (bottom - top - (marker_box[3] - marker_box[1])) / 2 - 1),
            marker,
            fill=(255, 255, 255, 255),
            font=font,
        )
        fallback_entries.append((index + 1, detection))

    if fallback_entries:
        legend_font = _annotation_font(max(600, image.width // 2))
        line_height = max(18, legend_font.getbbox("Ag")[3] + 5)
        legend_width = max(
            180,
            max(
                draw.textbbox(
                    (0, 0),
                    f"{number}. {item['class_name']} {item['confidence']:.0%}",
                    font=legend_font,
                )[2] + 14
                for number, item in fallback_entries
            ),
        )
        legend_height = line_height * len(fallback_entries) + 10
        legend_left = max(0, image.width - legend_width - 8)
        legend_top = max(0, image.height - legend_height - 8)
        draw.rounded_rectangle(
            [legend_left, legend_top, legend_left + legend_width, legend_top + legend_height],
            radius=4,
            fill=(10, 18, 30, 220),
            outline=(255, 255, 255, 190),
            width=1,
        )
        for line, (number, item) in enumerate(fallback_entries):
            draw.text(
                (legend_left + 7, legend_top + 5 + line * line_height),
                f"{number}. {item['class_name']} {item['confidence']:.0%}",
                fill=(255, 255, 255, 255),
                font=legend_font,
            )
    return image


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

    # Keep model rendering compatibility while using collision-aware labels for the API image.
    _plot_filtered_result(result, kept_indices)
    annotated_rgb = _draw_annotations(image.copy(), detections)
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
