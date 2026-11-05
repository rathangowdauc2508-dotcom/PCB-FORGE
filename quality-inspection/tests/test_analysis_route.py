from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routes import analysis
from app.schemas import ImageInput


def test_auto_uses_gemini_if_only_gemini_makes_status_ready(monkeypatch):
    monkeypatch.setattr(analysis, "load_image_bytes", lambda *_args: b"image")
    monkeypatch.setattr(analysis, "detector_status", lambda: {
        "ultralytics_installed": False,
        "weights_found": False,
        "ready": True,  # Gemini is configured; this must not imply YOLO is ready.
    })

    class FakeEngine:
        gemini = object()

        @staticmethod
        def _pick_model(_requested):
            return "gemini-test-vision"

    monkeypatch.setattr(analysis, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(analysis, "inspect_photo_with_gemma", lambda *_args: {"model_name": "gemini-test-vision"})
    monkeypatch.setattr(analysis, "detect_pcb_defects", lambda *_args: pytest.fail("YOLO must not run without weights"))

    request = analysis.PCBDetectionRequest(
        image=ImageInput(mime_type="image/png", base64_data="aW1hZ2U="),
        engine="auto",
    )
    assert analysis.detect_uploaded_pcb(request)["model_name"] == "gemini-test-vision"


def test_explicit_trained_engine_reports_missing_weights(monkeypatch):
    monkeypatch.setattr(analysis, "load_image_bytes", lambda *_args: b"image")
    monkeypatch.setattr(analysis, "detector_status", lambda: {
        "ultralytics_installed": False,
        "weights_found": False,
        "ready": True,
    })
    request = analysis.PCBDetectionRequest(
        image=ImageInput(mime_type="image/png", base64_data="aW1hZ2U="),
        engine="trained",
    )
    with pytest.raises(HTTPException) as error:
        analysis.detect_uploaded_pcb(request)
    assert error.value.status_code == 503
    assert "trained PCB detector is not ready" in error.value.detail
