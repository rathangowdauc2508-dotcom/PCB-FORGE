from __future__ import annotations

from app.diff_engine import compute_diff


def detect_diff_bbox(
    design_image_bytes: bytes,
    tested_image_bytes: bytes,
    *,
    threshold: int = 28,
    min_pixels: int = 20,
    padding: int = 6,
) -> dict | None:
    """Detect the largest diff region between design and tested images.

    Thin wrapper around :func:`compute_diff` that returns the single largest
    region as a ``dict`` compatible with the orchestrator contract.
    """
    try:
        regions = compute_diff(
            design_image_bytes,
            tested_image_bytes,
            threshold=threshold,
            min_area=min_pixels,
            padding=padding,
        )
    except ValueError:
        return None

    if not regions:
        return None

    # Pick the region with the largest area
    largest = max(regions, key=lambda r: r.area)
    box = largest.bounding_box

    # Compute confidence from area ratio
    confidence = min(0.99, max(0.1, largest.area / 10000.0 + 0.25))

    return {
        "label": "diff_hotspot",
        "x1": box.x_min,
        "y1": box.y_min,
        "x2": box.x_max,
        "y2": box.y_max,
        "confidence": round(confidence, 3),
    }
