from pathlib import Path

from app.vision_diff import detect_diff_bbox


def test_detect_diff_bbox_from_demo_assets() -> None:
    template = Path("data/assets/template_board.png").read_bytes()
    tested = Path("data/assets/tested_board.png").read_bytes()

    bbox = detect_diff_bbox(template, tested)

    assert bbox is not None
    assert bbox["x1"] < bbox["x2"]
    assert bbox["y1"] < bbox["y2"]
    assert 0.0 <= bbox["confidence"] <= 1.0
