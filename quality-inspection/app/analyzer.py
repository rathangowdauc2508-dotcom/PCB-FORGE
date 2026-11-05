from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from .diff_engine import compute_diff
from .gemini_client import GeminiService
from .image_utils import composite_crops, draw_bounding_boxes, image_to_base64
from .schemas import AnalysisResult, DefectBoundingBox, DetectedDefect

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path("data/templates")
TEMPLATE_FILE = TEMPLATE_DIR / "template.png"


def save_template(image_bytes: bytes) -> None:
    """Save the reference template image to disk as PNG."""
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    TEMPLATE_FILE.write_bytes(buf.getvalue())


def load_template() -> bytes:
    """Load the stored template image bytes."""
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError("No template image has been uploaded")
    return TEMPLATE_FILE.read_bytes()


def template_exists() -> bool:
    """Check if a template image has been saved."""
    return TEMPLATE_FILE.exists()


async def analyze_test_image(
    test_bytes: bytes,
    gemini_service: GeminiService,
    model: str = "gemma-4-31b-it",
) -> AnalysisResult:
    """Analyze a test image by diffing against the stored template.

    Unlike the pcb-analysis standalone version, this accepts a
    :class:`GeminiService` instance to leverage the multi-key pool.
    """
    template_bytes = load_template()
    template_b64 = image_to_base64(template_bytes)

    # Ensure test image is PNG
    img = Image.open(io.BytesIO(test_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    test_png = buf.getvalue()

    # Compute diff regions
    regions = compute_diff(template_bytes, test_png)

    if not regions:
        return AnalysisResult(
            defects=[],
            total_defects=0,
            template_image=template_b64,
            annotated_image=image_to_base64(test_png),
            diff_summary="No differences detected between template and test image.",
        )

    # Classify each diff region and get annotated crops
    defects: list[DetectedDefect] = []
    annotated_crops: list[tuple[DefectBoundingBox, bytes]] = []
    all_annotated = True

    for region in regions:
        classification = gemini_service.classify_crop(
            crop_raw=region.crop_raw,
            crop_highlighted=region.crop_highlighted,
            model=model,
        )

        defect_bbox = DefectBoundingBox(
            x_min=region.bounding_box.x_min,
            y_min=region.bounding_box.y_min,
            x_max=region.bounding_box.x_max,
            y_max=region.bounding_box.y_max,
        )

        defect = DetectedDefect(
            defect_type=classification.defect_type,
            description=classification.description,
            severity=classification.severity,
            bounding_box=defect_bbox,
        )
        defects.append(defect)

        annotated_crop = gemini_service.annotate_crop(
            crop_bytes=region.crop_highlighted,
            defect_type=classification.defect_type,
            severity=classification.severity.value,
            description=classification.description,
            model=model,
        )

        if annotated_crop is not None:
            annotated_crops.append((defect_bbox, annotated_crop))
        else:
            all_annotated = False

    # Composite annotated crops or fall back to Pillow drawing
    if annotated_crops and all_annotated:
        annotated_b64 = composite_crops(test_png, annotated_crops)
    else:
        logger.info("Gemini crop annotation incomplete, falling back to Pillow")
        annotated_b64 = draw_bounding_boxes(test_png, defects)

    diff_summary = (
        f"Found {len(regions)} difference region(s) between template and test image. "
        f"Total diff area: {sum(r.area for r in regions)} pixels."
    )

    return AnalysisResult(
        defects=defects,
        total_defects=len(defects),
        template_image=template_b64,
        annotated_image=annotated_b64,
        diff_summary=diff_summary,
    )
