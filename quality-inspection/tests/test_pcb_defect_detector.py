from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app import pcb_defect_detector as detector


EXPECTED_NAMES = {
    0: "BMFO",
    1: "CFO",
    2: "CS",
    3: "HB",
    4: "MB",
    5: "OP",
    6: "SC",
    7: "SH",
    8: "SP",
}


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
    def __init__(self, xyxy, classes, confidences):
        self.xyxy = _TensorLike(xyxy)
        self.cls = _TensorLike(classes)
        self.conf = _TensorLike(confidences)

    def __len__(self):
        return len(self.cls.values)

    def __getitem__(self, indices):
        return _BoxSet(
            [self.xyxy.values[index] for index in indices],
            [self.cls.values[index] for index in indices],
            [self.conf.values[index] for index in indices],
        )


class _Prediction:
    def __init__(self, boxes: _BoxSet):
        self.boxes = boxes
        self.plotted_class_ids: list[int] = []

    def plot(self):
        self.plotted_class_ids = list(self.boxes.cls.values)
        return np.zeros((32, 48, 3), dtype=np.uint8)


def _mock_weights(monkeypatch, tmp_path: Path) -> Path:
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test placeholder; model loading is mocked")
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(weights))
    return weights


def test_detect_returns_real_boxes_and_annotated_image(monkeypatch, tmp_path: Path):
    _mock_weights(monkeypatch, tmp_path)
    prediction = _Prediction(_BoxSet([[2, 3, 20, 22]], [1], [0.91]))

    class FakeModel:
        names = EXPECTED_NAMES

        @staticmethod
        def predict(**kwargs):
            assert kwargs["conf"] == detector.MIN_CONFIDENCE_THRESHOLD == 0.22
            assert kwargs["imgsz"] == 640
            assert kwargs["device"] == "cpu"
            assert kwargs["source"].shape == (32, 48, 3)
            assert kwargs["source"][0, 0].tolist() == [43, 69, 23]
            return [prediction]

    monkeypatch.setattr(detector, "_load_model", lambda _path: FakeModel())
    result = detector.detect_pcb_defects(_image_bytes())

    assert result["detections"] == [{
        "id": 1,
        "class_name": "CFO",
        "confidence": 0.91,
        "bbox": {"x1": 2.0, "y1": 3.0, "x2": 20.0, "y2": 22.0},
    }]
    assert result["image_width"] == 48
    assert result["image_height"] == 32
    assert result["annotated_image_base64"]
    assert prediction.plotted_class_ids == [1]


def test_all_nine_classes_use_per_class_thresholds_after_inference(monkeypatch, tmp_path: Path):
    _mock_weights(monkeypatch, tmp_path)
    coordinates = []
    class_ids = []
    confidences = []
    for class_id, threshold in detector.CLASS_CONFIDENCE_THRESHOLDS.items():
        coordinates.extend([[class_id, 1, class_id + 10, 11], [class_id, 2, class_id + 10, 12]])
        class_ids.extend([class_id, class_id])
        confidences.extend([threshold, threshold - 0.01])
    prediction = _Prediction(_BoxSet(coordinates, class_ids, confidences))

    class FakeModel:
        names = EXPECTED_NAMES

        @staticmethod
        def predict(**kwargs):
            assert kwargs["conf"] == 0.22
            return [prediction]

    monkeypatch.setattr(detector, "_load_model", lambda _path: FakeModel())
    result = detector.detect_pcb_defects(_image_bytes())

    assert [item["id"] for item in result["detections"]] == list(range(1, 10))
    assert [item["class_name"] for item in result["detections"]] == list(EXPECTED_NAMES.values())
    assert [item["confidence"] for item in result["detections"]] == list(
        detector.CLASS_CONFIDENCE_THRESHOLDS.values()
    )
    assert prediction.plotted_class_ids == list(range(9))


def test_legacy_global_threshold_cannot_discard_lower_threshold_classes(monkeypatch, tmp_path: Path):
    _mock_weights(monkeypatch, tmp_path)
    prediction = _Prediction(_BoxSet([], [], []))

    class FakeModel:
        names = EXPECTED_NAMES

        @staticmethod
        def predict(**kwargs):
            assert kwargs["conf"] == 0.22
            return [prediction]

    monkeypatch.setattr(detector, "_load_model", lambda _path: FakeModel())
    detector.detect_pcb_defects(_image_bytes(), confidence_threshold=0.90)


def test_detector_status_reports_nine_class_configuration(monkeypatch, tmp_path: Path):
    weights = _mock_weights(monkeypatch, tmp_path)
    status = detector.detector_status()

    assert status["weights_path"] == str(weights)
    assert status["class_count"] == 9
    assert status["required_classes"] == list(EXPECTED_NAMES.values())
    assert status["confidence_thresholds"] == {
        EXPECTED_NAMES[class_id]: threshold
        for class_id, threshold in detector.CLASS_CONFIDENCE_THRESHOLDS.items()
    }


def test_missing_weights_fail_explicitly(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PCB_DEFECT_MODEL_PATH", str(tmp_path / "missing.pt"))
    with pytest.raises(FileNotFoundError, match="trained best.pt"):
        detector.detect_pcb_defects(_image_bytes())


@pytest.mark.parametrize(
    "names",
    [
        {0: "BMFO"},
        {**EXPECTED_NAMES, 0: "CFO", 1: "BMFO"},
        {**EXPECTED_NAMES, 8: "sp"},
    ],
)
def test_incompatible_model_classes_are_rejected(names, monkeypatch, tmp_path: Path):
    _mock_weights(monkeypatch, tmp_path)

    class WrongModel:
        pass

    WrongModel.names = names
    monkeypatch.setattr(detector, "_load_model", lambda _path: WrongModel())
    with pytest.raises(detector.DetectorModelError, match="nine-class"):
        detector.detect_pcb_defects(_image_bytes())


@pytest.mark.parametrize("payload", [b"", b"not an image"])
def test_invalid_image_is_rejected(payload: bytes, monkeypatch, tmp_path: Path):
    _mock_weights(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        detector.detect_pcb_defects(payload)
