from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app import pcb_defect_detector as detector


def _image_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (48, 32), "#17452b").save(stream, format="PNG")
    return stream.getvalue()


class _TensorLike:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class _BoxSet:
    xyxy = _TensorLike([[2, 3, 20, 22]])
    cls = _TensorLike([1])
    conf = _TensorLike([0.91])

    def __len__(self):
        return 1


class _Prediction:
    names = {1: "open_circuit"}
    boxes = _BoxSet()

    @staticmethod
    def plot():
        return np.zeros((32, 48, 3), dtype=np.uint8)


def test_detect_returns_real_boxes_and_annotated_image(monkeypatch, tmp_path: Path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test placeholder; model loading is mocked")
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(weights))

    class FakeModel:
        names = {
            0: "missing hole", 1: "mouse bite", 2: "open circuit",
            3: "short", 4: "spur", 5: "spurious copper",
        }

        @staticmethod
        def predict(**kwargs):
            assert kwargs["imgsz"] == 640
            assert kwargs["device"] == "cpu"
            assert kwargs["source"].shape == (32, 48, 3)
            return [_Prediction()]

    monkeypatch.setattr(detector, "_load_model", lambda _path: FakeModel())
    result = detector.detect_pcb_defects(_image_bytes())

    assert result["detections"] == [{
        "id": 1,
        "class_name": "open_circuit",
        "confidence": 0.91,
        "bbox": {"x1": 2.0, "y1": 3.0, "x2": 20.0, "y2": 22.0},
    }]
    assert result["image_width"] == 48
    assert result["image_height"] == 32
    assert result["annotated_image_base64"]


def test_missing_weights_fail_explicitly(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(tmp_path / "missing.pt"))
    with pytest.raises(FileNotFoundError, match="trained best.pt"):
        detector.detect_pcb_defects(_image_bytes())


def test_incompatible_model_classes_are_rejected(monkeypatch, tmp_path: Path):
    weights = tmp_path / "wrong-model.pt"
    weights.write_bytes(b"placeholder")
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(weights))

    class WrongModel:
        names = {0: "person"}

    monkeypatch.setattr(detector, "_load_model", lambda _path: WrongModel())
    with pytest.raises(detector.DetectorModelError, match="do not match"):
        detector.detect_pcb_defects(_image_bytes())


@pytest.mark.parametrize("payload", [b"", b"not an image"])
def test_invalid_image_is_rejected(payload: bytes, monkeypatch, tmp_path: Path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"placeholder")
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(weights))
    with pytest.raises(ValueError):
        detector.detect_pcb_defects(payload)
