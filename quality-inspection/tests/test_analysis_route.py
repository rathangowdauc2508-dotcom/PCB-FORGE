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


def test_trained_detection_endpoint_preserves_detector_response(monkeypatch):
    monkeypatch.setattr(analysis, "load_image_bytes", lambda *_args: b"image")
    monkeypatch.setattr(analysis, "detector_status", lambda: {
        "ultralytics_installed": True,
        "weights_found": True,
    })
    expected = {
        "model_name": "YOLOv8 PCB defect detector",
        "model_weights": "best.pt",
        "image_width": 640,
        "image_height": 480,
        "inference_ms": 25,
        "detections": [{
            "id": 1,
            "class_name": "BMFO",
            "confidence": 0.9,
            "bbox": {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0},
        }],
        "annotated_image_base64": "anBlZw==",
    }
    monkeypatch.setattr(analysis, "detect_pcb_defects", lambda image: expected if image == b"image" else None)
    request = analysis.PCBDetectionRequest(
        image=ImageInput(mime_type="image/png", base64_data="aW1hZ2U="),
        engine="trained",
    )

    assert analysis.detect_uploaded_pcb(request) == expected


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (analysis.DetectorModelError("wrong classes"), 503),
        (ValueError("bad image"), 400),
    ],
)
def test_trained_detection_endpoint_maps_detector_errors(monkeypatch, error, status_code):
    monkeypatch.setattr(analysis, "load_image_bytes", lambda *_args: b"image")
    monkeypatch.setattr(analysis, "detector_status", lambda: {
        "ultralytics_installed": True,
        "weights_found": True,
    })

    def fail(_image):
        raise error

    monkeypatch.setattr(analysis, "detect_pcb_defects", fail)
    request = analysis.PCBDetectionRequest(
        image=ImageInput(mime_type="image/png", base64_data="aW1hZ2U="),
        engine="trained",
    )
    with pytest.raises(HTTPException) as raised:
        analysis.detect_uploaded_pcb(request)
    assert raised.value.status_code == status_code


def test_detector_status_endpoint_keeps_nine_class_metadata(monkeypatch):
    monkeypatch.setattr(analysis, "detector_status", lambda: {
        "ultralytics_installed": True,
        "weights_found": True,
        "class_count": 9,
        "required_classes": ["BMFO", "CFO", "CS", "HB", "MB", "OP", "SC", "SH", "SP"],
        "confidence_thresholds": {"BMFO": 0.37, "MB": 0.22},
    })
    monkeypatch.setattr(analysis, "_gemma_available", lambda: False)

    status = analysis.get_pcb_detector_status()

    assert status["class_count"] == 9
    assert status["required_classes"][0] == "BMFO"
    assert status["required_classes"][-1] == "SP"
    assert status["confidence_thresholds"]["MB"] == 0.22
    assert status["yolo_ready"] is True
    assert status["backend"] == "yolo"
