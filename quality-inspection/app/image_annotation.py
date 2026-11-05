"""Draw bounding boxes with labels onto an image. Returns base64 PNG."""
from __future__ import annotations

import base64
import colorsys
import io

from PIL import Image, ImageDraw, ImageFont

from .diff_engine import DiffRegion
from .schemas import BoundingBox


def _pick_color(index: int, total: int) -> tuple[int, int, int]:
    if total == 0:
        return (255, 60, 90)
    hue = (index / max(total, 1)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.95)
    return (int(r * 255), int(g * 255), int(b * 255))


def _load_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_labels(
    draw: ImageDraw.ImageDraw,
    boxes: list[BoundingBox],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Draw borders and labels for each bounding box."""
    total = len(boxes)
    for i, box in enumerate(boxes):
        color = _pick_color(i, total)

        # Border (3 px)
        for offset in range(3):
            draw.rectangle(
                [box.x1 - offset, box.y1 - offset, box.x2 + offset, box.y2 + offset],
                outline=color,
            )

        # Label text
        conf_pct = f"{box.confidence * 100:.0f}%"
        label = f"{box.label}  {conf_pct}"
        bbox = font.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        label_y = max(0, box.y1 - text_h - 8)
        # Label background
        draw.rectangle(
            [box.x1, label_y, box.x1 + text_w + 8, label_y + text_h + 6],
            fill=color,
        )
        # Label text
        draw.text((box.x1 + 4, label_y + 3), label, fill="black", font=font)


def draw_boxes_on_image(
    image_bytes: bytes,
    boxes: list[BoundingBox],
    diff_regions: list[DiffRegion] | None = None,
) -> str:
    """Draw labeled bounding boxes on *image_bytes* and return base64 PNG.

    If *diff_regions* is provided, the highlighted diff crops are composited
    onto the image at their bounding box positions before drawing labels.
    This shows the magenta-highlighted pixel differences from the OpenCV
    diff engine rather than plain rectangles.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Paste highlighted diff crops onto the image
    if diff_regions:
        for region in diff_regions:
            bb = region.bounding_box
            crop = Image.open(io.BytesIO(region.crop_highlighted)).convert("RGB")
            target_w = bb.x_max - bb.x_min
            target_h = bb.y_max - bb.y_min
            if crop.size != (target_w, target_h):
                crop = crop.resize((target_w, target_h), Image.LANCZOS)
            img.paste(crop, (bb.x_min, bb.y_min))

    draw = ImageDraw.Draw(img, "RGBA")
    font = _load_font(14)

    # If no diff crops, add a semi-transparent fill so boxes are still visible
    if not diff_regions:
        total = len(boxes)
        for i, box in enumerate(boxes):
            color = _pick_color(i, total)
            fill_color = (*color, 40)
            draw.rectangle([box.x1, box.y1, box.x2, box.y2], fill=fill_color)

    _draw_labels(draw, boxes, font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
