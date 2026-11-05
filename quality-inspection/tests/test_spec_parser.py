from pathlib import Path

from app.spec_parser import build_spec_navigation_report, resolve_spec_excerpt, select_relevant_spec_excerpt


def test_select_relevant_spec_excerpt_prefers_keyword_lines() -> None:
    spec = "\n".join(
        [
            "General intro",
            "Keep copper traces clean.",
            "SDA line minimum clearance is 0.10mm.",
            "This avoids short and arbitration failure.",
            "Unrelated appendix",
        ]
    )
    excerpt = select_relevant_spec_excerpt(spec, "I2C SDA arbitration lost short")
    assert "SDA line minimum clearance" in excerpt


def test_resolve_spec_excerpt_from_document(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.txt"
    spec_file.write_text("Rule A\nPCIe spacing minimum 15mil\nRule B", encoding="utf-8")

    excerpt = resolve_spec_excerpt(
        spec_excerpt=None,
        spec_document_path=str(spec_file),
        error_log="PCIe link downgraded spacing",
        root_dir=tmp_path,
    )
    assert "PCIe spacing minimum 15mil" in excerpt


def test_build_spec_navigation_report_uses_toc_like_lines() -> None:
    spec = "\n".join(
        [
            "DEEP PCB SPEC",
            "",
            "1 Overview",
            "2 Functional Test",
            "2.1 SDA Net Requirements ..... 5",
            "2.2 GND Clearance ..... 12",
            "2.3 Signal Integrity ..... 20",
            "",
            "SDA net must not be shorted to adjacent nets.",
            "Spacing between SDA and GND must be > 0.15 mm.",
        ]
    )
    report = build_spec_navigation_report(spec, "I2C SDA line short detected")
    assert report["selected_sections"], "expected focused sections from TOC"
    assert any("SDA" in section for section in report["selected_sections"])
    assert report["toc"], "expected toc candidates parsed"


def test_build_spec_navigation_report_prefers_toc_marker_pages() -> None:
    spec = "\f".join(
        [
            "Arduino datasheet\nFront matter\n",
            "Contents\n1 Power tree overview ..... 1\n2 Power integrity ..... 4",
            "Detailed body starts.\n2.1 Power tree overview ..... 12\n",
            "Appendix\n2.2 Not TOC section ..... 34",
        ]
    )
    report = build_spec_navigation_report(spec, "power tree short")
    assert report["selected_sections"], "expected TOC sections selected from toc marker pages"
    assert "Power tree overview" in report["selected_sections"][0]
    assert "Not TOC" not in " ".join(report["selected_sections"])
