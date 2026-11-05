from pathlib import Path
import base64

from app.file_processing import (
    UploadedFileInput,
    _build_spec_navigation_bundle,
    _contains_toc_marker,
    _extract_spec_text_for_focus,
)


def _fixture_pdf(name: str) -> UploadedFileInput:
    data = Path("real-data") / name
    return UploadedFileInput(
        file_name=name,
        mime_type="application/pdf",
        base64_data=base64.b64encode(data.read_bytes()).decode("ascii"),
    )


def test_build_spec_navigation_bundle_uses_datasheet_only_when_present() -> None:
    datasheet = _fixture_pdf("A000066-datasheet.pdf")
    full_pinout = _fixture_pdf("A000066-full-pinout.pdf")
    schematics = _fixture_pdf("A000066-schematics.pdf")

    excerpt, _, _ = _build_spec_navigation_bundle(
        [full_pinout, schematics, datasheet],
        error_log="I2C communication error and SDA short",
    )

    assert "A000066-datasheet.pdf" in excerpt
    assert "A000066-full-pinout.pdf" not in excerpt
    assert "A000066-schematics.pdf" not in excerpt


def test_extract_spec_text_for_focus_uses_toc_pages_for_datasheet() -> None:
    datasheet = _fixture_pdf("A000066-datasheet.pdf")
    text = _extract_spec_text_for_focus(datasheet)

    assert text
    assert _contains_toc_marker(text)

