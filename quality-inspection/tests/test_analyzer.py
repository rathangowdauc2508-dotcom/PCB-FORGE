"""Tests for app.analyzer — the PCB analysis pipeline."""

import io
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.analyzer import analyze_test_image, save_template, template_exists
from app.schemas import GeminiDefectResponse, Severity


def _make_png(
    size: tuple[int, int] = (200, 150),
    color: tuple[int, int, int] = (100, 100, 100),
) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_with_rect(
    size: tuple[int, int] = (200, 150),
    bg_color: tuple[int, int, int] = (100, 100, 100),
    rect: tuple[int, int, int, int] = (50, 40, 100, 90),
    rect_color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    img = Image.new("RGB", size, bg_color)
    arr = np.array(img)
    x1, y1, x2, y2 = rect
    arr[y1:y2, x1:x2] = rect_color
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_gemini_service():
    """Build a mock GeminiService with classify_crop and annotate_crop."""
    svc = MagicMock()
    svc.classify_crop.return_value = GeminiDefectResponse(
        defect_type="short",
        description="Solder bridge detected",
        severity=Severity.HIGH,
    )
    svc.annotate_crop.return_value = None  # fallback to Pillow
    return svc


@pytest.fixture(autouse=True)
def _setup_template(tmp_path, monkeypatch):
    """Point template storage at a temp directory."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    monkeypatch.setattr("app.analyzer.TEMPLATE_DIR", template_dir)
    monkeypatch.setattr("app.analyzer.TEMPLATE_FILE", template_dir / "template.png")


@pytest.mark.asyncio
async def test_analyze_no_diff():
    """Identical images should produce zero defects."""
    img = _make_png()
    save_template(img)

    svc = _mock_gemini_service()
    result = await analyze_test_image(img, gemini_service=svc)

    assert result.total_defects == 0
    assert result.defects == []
    assert result.template_image != ""
    assert "No differences" in result.diff_summary
    svc.classify_crop.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_with_diff():
    """A modified image should produce defects."""
    template = _make_png()
    test = _make_png_with_rect(rect=(50, 40, 100, 90), rect_color=(255, 255, 255))
    save_template(template)

    svc = _mock_gemini_service()
    result = await analyze_test_image(test, gemini_service=svc)

    assert result.total_defects >= 1
    assert len(result.defects) >= 1
    assert result.defects[0].defect_type == "short"
    assert result.defects[0].severity == Severity.HIGH
    assert result.annotated_image != ""
    assert result.template_image != ""
    assert "difference region" in result.diff_summary
    svc.classify_crop.assert_called()
    svc.annotate_crop.assert_called()


@pytest.mark.asyncio
async def test_analyze_result_shape():
    """Result should have all expected fields."""
    template = _make_png()
    test = _make_png_with_rect(rect=(50, 40, 100, 90), rect_color=(255, 255, 255))
    save_template(template)

    svc = _mock_gemini_service()
    result = await analyze_test_image(test, gemini_service=svc)

    data = result.model_dump()
    assert "defects" in data
    assert "total_defects" in data
    assert "template_image" in data
    assert "annotated_image" in data
    assert "diff_summary" in data

    for defect in data["defects"]:
        assert "defect_type" in defect
        assert "description" in defect
        assert "severity" in defect
        assert "bounding_box" in defect
        bb = defect["bounding_box"]
        assert all(k in bb for k in ("x_min", "y_min", "x_max", "y_max"))


def test_template_save_and_exists():
    """Template should be saveable and detectable."""
    assert not template_exists()
    save_template(_make_png())
    assert template_exists()
