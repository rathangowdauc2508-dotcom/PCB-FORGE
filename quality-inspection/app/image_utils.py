from __future__ import annotations

import base64
import io

from PIL import Image, ImageDraw, ImageFont

from .schemas import DefectBoundingBox, DetectedDefect


def _generate_color(index: int, total: int) -> tuple[int, int, int]:
    """Generate a distinct color using HSV rotation."""
    import colorsys

    if total == 0:
        return (255, 0, 0)
    hue = (index / max(total, 1)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.95)
    return (int(r * 255), int(g * 255), int(b * 255))


def draw_bounding_boxes(
    image_bytes: bytes, defects: list[DetectedDefect]
) -> str:
    """Draw labeled bounding boxes on the image and return base64 PNG.

    Used as a fallback when Gemini annotation is unavailable.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except OSError:
            font = ImageFont.load_default()

    total = len(defects)
    for i, defect in enumerate(defects):
        color = _generate_color(i, total)
        box = defect.bounding_box

        for offset in range(3):
            draw.rectangle(
                [box.x_min - offset, box.y_min - offset, box.x_max + offset, box.y_max + offset],
                outline=color,
            )

        label = f"{defect.defect_type} [{defect.severity.value}]"
        bbox = font.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        label_y = max(0, box.y_min - text_h - 6)
        draw.rectangle(
            [box.x_min, label_y, box.x_min + text_w + 4, label_y + text_h + 4],
            fill=color,
        )
        draw.text((box.x_min + 2, label_y + 2), label, fill="black", font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def composite_crops(
    image_bytes: bytes,
    annotated_crops: list[tuple[DefectBoundingBox, bytes]],
) -> str:
    """Paste annotated crops back onto the original image at their bounding box positions.

    Returns base64-encoded PNG.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    for bbox, crop_bytes in annotated_crops:
        crop = Image.open(io.BytesIO(crop_bytes)).convert("RGB")
        target_w = bbox.x_max - bbox.x_min
        target_h = bbox.y_max - bbox.y_min
        if crop.size != (target_w, target_h):
            crop = crop.resize((target_w, target_h), Image.LANCZOS)
        img.paste(crop, (bbox.x_min, bbox.y_min))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode()


GEMMA_MAX_SIDE = 1568


def normalize_for_gemma(image_bytes: bytes, declared_mime: str | None = None) -> tuple[bytes, str]:
    """Return (bytes, mime) that Gemma will accept.

    The browser's declared MIME type is not trustworthy (BMP, mislabeled files,
    CMYK/palette/16-bit images, huge scans all cause 400 INVALID_ARGUMENT), so
    decode with Pillow, flatten to RGB, cap the longest side, and re-encode.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as exc:
        raise ValueError(
            f"Could not decode the uploaded image (declared type {declared_mime!r}). "
            "Upload a real PNG, JPG, or WEBP board image."
        ) from exc

    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    if max(img.size) > GEMMA_MAX_SIDE:
        img.thumbnail((GEMMA_MAX_SIDE, GEMMA_MAX_SIDE), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue(), "image/jpeg"