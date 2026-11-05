"""Tests for the PCB analysis schemas added to app/schemas.py."""

import json

from app.schemas import (
    AnalysisResult,
    DefectBoundingBox,
    DetectedDefect,
    GeminiDefectResponse,
    Severity,
)


def test_severity_enum_values():
    assert Severity.LOW == "low"
    assert Severity.MEDIUM == "medium"
    assert Severity.HIGH == "high"


def test_defect_bounding_box_creation():
    box = DefectBoundingBox(x_min=10, y_min=20, x_max=100, y_max=200)
    assert box.x_min == 10
    assert box.y_min == 20
    assert box.x_max == 100
    assert box.y_max == 200


def test_gemini_defect_response_roundtrip():
    resp = GeminiDefectResponse(
        defect_type="open_circuit",
        description="Break in copper trace",
        severity=Severity.HIGH,
    )
    data = json.loads(resp.model_dump_json())
    assert data["defect_type"] == "open_circuit"
    assert data["severity"] == "high"
    reparsed = GeminiDefectResponse.model_validate(data)
    assert reparsed == resp


def test_detected_defect_with_bounding_box():
    defect = DetectedDefect(
        defect_type="short",
        description="Solder bridge",
        severity=Severity.MEDIUM,
        bounding_box=DefectBoundingBox(x_min=5, y_min=10, x_max=50, y_max=60),
    )
    assert defect.bounding_box.x_min == 5
    assert defect.severity == Severity.MEDIUM


def test_analysis_result_defaults():
    result = AnalysisResult()
    assert result.defects == []
    assert result.total_defects == 0
    assert result.template_image == ""
    assert result.annotated_image == ""
    assert result.diff_summary == ""


def test_analysis_result_with_defects():
    defect = DetectedDefect(
        defect_type="mouse_bite",
        description="Irregular edge on pad",
        severity=Severity.LOW,
        bounding_box=DefectBoundingBox(x_min=0, y_min=0, x_max=30, y_max=30),
    )
    result = AnalysisResult(
        defects=[defect],
        total_defects=1,
        template_image="base64data",
        annotated_image="base64annotated",
        diff_summary="1 defect region found",
    )
    data = json.loads(result.model_dump_json())
    assert data["total_defects"] == 1
    assert len(data["defects"]) == 1
    assert data["defects"][0]["defect_type"] == "mouse_bite"


def test_analysis_result_json_schema():
    schema = AnalysisResult.model_json_schema()
    assert "defects" in schema["properties"]
    assert "total_defects" in schema["properties"]
