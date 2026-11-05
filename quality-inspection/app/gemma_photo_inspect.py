"""Single-photo PCB defect inspection with ONE Gemma vision call (no YOLO weights needed).

Returns the same shape as pcb_defect_detector.detect_pcb_defects so the UI is unchanged.
"""
from __future__ import annotations

import base64
import io
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .image_utils import normalize_for_gemma

MAX_IMAGE_BYTES = 20 * 1024 * 1024
OUT_MAX_SIDE = 1600
CLASSES = ["missing_hole", "mouse_bite", "open_circuit", "short", "spur", "spurious_copper", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "defects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": CLASSES},
                    "confidence": {"type": "number"},
                    "box_2d": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["label", "confidence", "box_2d"],
            },
        }
    },
    "required": ["defects"],
}

PROMPT = (
    "You are a PCB visual inspector. Look at this single board photo and list ONLY clearly visible "
    "manufacturing defects (max 8). Allowed labels: " + ", ".join(CLASSES) + ". "
    "For each, give box_2d as [ymin, xmin, ymax, xmax] integers normalized to 0-1000 relative to the "
    "image, and confidence 0-1. Do not guess electrical faults. If you see no clear defect, return "
    '{"defects": []}.'
)


def _clamp_box(raw: Any) -> tuple[int, int, int, int] | None:
    try:
        y1, x1, y2, x2 = [float(v) for v in raw[:4]]
    except Exception:
        return None
    y1, y2 = sorted((max(0.0, min(1000.0, y1)), max(0.0, min(1000.0, y2))))
    x1, x2 = sorted((max(0.0, min(1000.0, x1)), max(0.0, min(1000.0, x2))))
    if y2 - y1 < 5 or x2 - x1 < 5:
        return None
    return int(y1), int(x1), int(y2), int(x2)


def inspect_photo_with_gemma(gemini, model: str, image_bytes: bytes, *, temperature: float = 0.1) -> dict[str, Any]:
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image is too large. Maximum upload size is 20 MB.")

    send_bytes, send_mime = normalize_for_gemma(image_bytes, None)  # raises ValueError if not an image
    started = time.perf_counter()
    data = gemini.generate_json(
        model=model,
        prompt=PROMPT,
        response_schema=SCHEMA,
        temperature=temperature,
        max_output_tokens=1024,
        image_parts=[(send_bytes, send_mime)],
        task_name="Photo Inspector",
    )
    inference_ms = round((time.perf_counter() - started) * 1000)

    image = Image.open(io.BytesIO(send_bytes)).convert("RGB")
    if max(image.size) > OUT_MAX_SIDE:
        image.thumbnail((OUT_MAX_SIDE, OUT_MAX_SIDE), Image.LANCZOS)
    w, h = image.size
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(12, w // 70))
    except OSError:
        font = ImageFont.load_default()

    detections: list[dict[str, Any]] = []
    for item in (data.get("defects") or [])[:8]:
        box = _clamp_box(item.get("box_2d") or [])
        if box is None:
            continue
        y1, x1, y2, x2 = box
        label = str(item.get("label") or "other")
        if label not in CLASSES:
            label = "other"
        try:
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        px = (round(x1 * w / 1000, 1), round(y1 * h / 1000, 1), round(x2 * w / 1000, 1), round(y2 * h / 1000, 1))
        detections.append({
            "id": len(detections) + 1,
            "class_name": label,
            "confidence": round(conf, 4),
            "bbox": {"x1": px[0], "y1": px[1], "x2": px[2], "y2": px[3]},
        })
        draw.rectangle(px, outline=(255, 40, 40), width=max(2, w // 400))
        text = f"{label} {conf:.0%}"
        draw.rectangle([px[0], max(0, px[1] - font.size - 4), px[0] + len(text) * font.size * 0.62, px[1]], fill=(255, 40, 40))
        draw.text((px[0] + 2, max(0, px[1] - font.size - 3)), text, fill="white", font=font)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88, optimize=True)
    return {
        "model_name": f"Gemini vision · {model} (single call; scores are model-reported)",
        "model_weights": model,
        "image_width": w,
        "image_height": h,
        "inference_ms": inference_ms,
        "detections": detections,
        "annotated_image_base64": base64.b64encode(out.getvalue()).decode("ascii"),
    }
