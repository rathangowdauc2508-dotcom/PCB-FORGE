from __future__ import annotations

import pytest

from app.file_processing import _build_grouped_case_mappings
from app.schemas import ImageInput


def _img(path: str) -> ImageInput:
    return ImageInput(mime_type="image/png", file_path=path)


def test_grouped_mappings_non_strict_reuses_last_item() -> None:
    mappings = _build_grouped_case_mappings(
        error_logs=["e1", "e2", "e3"],
        design_images=[_img("d1.png")],
        tested_images=[_img("t1.png"), _img("t2.png")],
        spec_excerpts=["spec-a"],
        spec_document_paths=[],
        strict=False,
    )

    assert len(mappings) == 3
    assert mappings[0].error_log_index == 0
    assert mappings[1].error_log_index == 1
    assert mappings[2].error_log_index == 2
    assert mappings[2].design_image_index == 0
    assert mappings[2].tested_image_index == 1
    assert mappings[2].spec_source_type == "spec_excerpt"
    assert mappings[2].spec_source_index == 0


def test_grouped_mappings_strict_missing_index_raises() -> None:
    with pytest.raises(ValueError):
        _build_grouped_case_mappings(
            error_logs=["e1", "e2"],
            design_images=[_img("d1.png")],
            tested_images=[_img("t1.png"), _img("t2.png")],
            spec_excerpts=["spec-a", "spec-b"],
            spec_document_paths=[],
            strict=True,
        )
