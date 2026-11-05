"""Tests for classify_crop and annotate_crop methods on GeminiService."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from PIL import Image

from app.gemini_client import GeminiService
from app.schemas import GeminiDefectResponse, Severity


def _make_png(size=(50, 50), color=(128, 128, 128)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_service() -> GeminiService:
    return GeminiService(api_keys=["fake-key-1"])


# ---- classify_crop tests ----

def test_classify_crop_success():
    """classify_crop returns a GeminiDefectResponse on success."""
    service = _build_service()

    mock_response = MagicMock()
    mock_response.text = '{"defect_type":"short","description":"Solder bridge","severity":"high"}'

    with patch.object(service, "_with_retry", return_value=GeminiDefectResponse(
        defect_type="short",
        description="Solder bridge",
        severity=Severity.HIGH,
    )):
        result = service.classify_crop(_make_png(), _make_png())

    assert isinstance(result, GeminiDefectResponse)
    assert result.defect_type == "short"
    assert result.severity == Severity.HIGH


def test_classify_crop_fallback_on_error():
    """classify_crop returns a default response on API failure."""
    service = _build_service()

    with patch.object(service, "_with_retry", side_effect=RuntimeError("API down")):
        result = service.classify_crop(_make_png(), _make_png())

    assert isinstance(result, GeminiDefectResponse)
    assert result.defect_type == "unknown"
    assert "failed" in result.description.lower()


# ---- annotate_crop tests ----

def test_annotate_crop_success():
    """annotate_crop returns image bytes on success."""
    service = _build_service()
    fake_image_bytes = _make_png()

    with patch.object(service, "_with_retry", return_value=fake_image_bytes):
        result = service.annotate_crop(
            _make_png(),
            defect_type="open_circuit",
            severity="high",
            description="Break in trace",
        )

    assert result == fake_image_bytes


def test_annotate_crop_returns_none_on_error():
    """annotate_crop returns None on API failure."""
    service = _build_service()

    with patch.object(service, "_with_retry", side_effect=RuntimeError("API down")):
        result = service.annotate_crop(
            _make_png(),
            defect_type="short",
            severity="medium",
            description="Bridge",
        )

    assert result is None


def test_annotate_crop_returns_none_when_no_image():
    """annotate_crop returns None when Gemini returns no image."""
    service = _build_service()

    with patch.object(service, "_with_retry", return_value=None):
        result = service.annotate_crop(
            _make_png(),
            defect_type="mouse_bite",
            severity="low",
            description="Edge nibble",
        )

    assert result is None
