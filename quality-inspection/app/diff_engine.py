from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np

# Default tuning constants (can be overridden per-call)
DIFF_THRESHOLD = 30
MIN_CONTOUR_AREA = 100
CROP_PADDING = 20


@dataclass
class DiffBoundingBox:
    x_min: int
    y_min: int
    x_max: int
    y_max: int


@dataclass
class DiffRegion:
    bounding_box: DiffBoundingBox
    crop_raw: bytes
    crop_highlighted: bytes
    area: int


def _merge_overlapping_rects(
    rects: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """Merge overlapping or nearby bounding rectangles."""
    if not rects:
        return []

    merged = list(rects)
    changed = True
    while changed:
        changed = False
        new_merged: list[tuple[int, int, int, int]] = []
        used = [False] * len(merged)
        for i in range(len(merged)):
            if used[i]:
                continue
            x1, y1, x2, y2 = merged[i]
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                ox1, oy1, ox2, oy2 = merged[j]
                # Check overlap (including touching)
                if x1 <= ox2 and x2 >= ox1 and y1 <= oy2 and y2 >= oy1:
                    x1 = min(x1, ox1)
                    y1 = min(y1, oy1)
                    x2 = max(x2, ox2)
                    y2 = max(y2, oy2)
                    used[j] = True
                    changed = True
            new_merged.append((x1, y1, x2, y2))
            used[i] = True
        merged = new_merged

    return merged


def compute_diff(
    template_bytes: bytes,
    test_bytes: bytes,
    threshold: int = DIFF_THRESHOLD,
    min_area: int = MIN_CONTOUR_AREA,
    padding: int = CROP_PADDING,
) -> list[DiffRegion]:
    """Compute pixel differences between template and test images.

    Returns a list of DiffRegion objects with highlighted crops.
    """
    # Decode images
    template_arr = np.frombuffer(template_bytes, dtype=np.uint8)
    template_bgr = cv2.imdecode(template_arr, cv2.IMREAD_COLOR)

    test_arr = np.frombuffer(test_bytes, dtype=np.uint8)
    test_bgr = cv2.imdecode(test_arr, cv2.IMREAD_COLOR)

    if template_bgr is None or test_bgr is None:
        raise ValueError("Failed to decode one or both images")

    if template_bgr.shape != test_bgr.shape:
        raise ValueError(
            f"Image dimensions must match: template={template_bgr.shape[:2]}, "
            f"test={test_bgr.shape[:2]}"
        )

    h, w = template_bgr.shape[:2]

    # Convert to grayscale and compute absolute difference
    template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
    test_gray = cv2.cvtColor(test_bgr, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(template_gray, test_gray)

    # Threshold
    _, binary = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)

    # Morphological operations to clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by area and collect bounding rects
    rects: list[tuple[int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        # Add padding
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w, x + cw + padding)
        y2 = min(h, y + ch + padding)
        rects.append((x1, y1, x2, y2))

    # Merge overlapping rectangles
    merged_rects = _merge_overlapping_rects(rects)

    # Create highlighted crops for each region
    regions: list[DiffRegion] = []
    for x1, y1, x2, y2 in merged_rects:
        # Crop the test image
        crop = test_bgr[y1:y2, x1:x2].copy()

        # Create magenta highlight overlay on diff pixels within this crop
        crop_mask = binary[y1:y2, x1:x2]
        overlay = crop.copy()
        # Magenta color in BGR
        overlay[crop_mask > 0] = [255, 0, 255]
        # Blend: 60% original, 40% overlay
        highlighted = cv2.addWeighted(crop, 0.6, overlay, 0.4, 0)

        # Encode crops as PNG
        _, raw_png = cv2.imencode(".png", crop)
        _, highlighted_png = cv2.imencode(".png", highlighted)

        region_area = int(np.sum(crop_mask > 0))

        regions.append(
            DiffRegion(
                bounding_box=DiffBoundingBox(x_min=x1, y_min=y1, x_max=x2, y_max=y2),
                crop_raw=raw_png.tobytes(),
                crop_highlighted=highlighted_png.tobytes(),
                area=region_area,
            )
        )

    return regions
