"""Integration tests — HTTP-level round-trips through the FastAPI app."""

from __future__ import annotations

import io
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


@pytest.fixture
def client():
    """Create a TestClient that triggers startup."""
    # Patch so startup doesn't need real API keys
    with patch("app.main.get_settings") as mock_settings:
        settings = MagicMock()
        settings.gemini_api_keys = []
        settings.request_timeout_sec = 10
        settings.default_model = "gemma-4"
        mock_settings.return_value = settings

        with TestClient(app) as c:
            yield c


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "time_utc" in data


def test_health_shows_key_status(client):
    resp = client.get("/health")
    data = resp.json()
    assert "gemini_api_key_configured" in data
    assert "gemini_key_count" in data


def test_models_requires_engine(client):
    """Without API keys, /models should return 503."""
    resp = client.get("/models")
    assert resp.status_code == 503


def test_orchestrate_requires_engine(client):
    """Without API keys, /orchestrate should return 503."""
    resp = client.post("/orchestrate", json={
        "input": {
            "error_log": "test error",
            "spec_excerpt": "test spec",
            "design_image": {"mime_type": "image/png", "file_path": "data/assets/template_board.png"},
            "tested_image": {"mime_type": "image/png", "file_path": "data/assets/tested_board.png"},
        },
    })
    assert resp.status_code == 503


def test_analysis_template_get(client):
    """GET /analysis/template should work even without a template."""
    resp = client.get("/analysis/template")
    assert resp.status_code == 200
    data = resp.json()
    assert "exists" in data


def test_analysis_template_post(client, tmp_path, monkeypatch):
    """POST /analysis/template should accept an image upload."""
    monkeypatch.setattr("app.analyzer.TEMPLATE_DIR", tmp_path)
    monkeypatch.setattr("app.analyzer.TEMPLATE_FILE", tmp_path / "template.png")

    img = Image.new("RGB", (50, 50), (200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post(
        "/analysis/template",
        files={"file": ("template.png", buf, "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_analysis_analyze_requires_template(client):
    """POST /analysis/analyze should fail if no template exists."""
    img = Image.new("RGB", (50, 50), (100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post(
        "/analysis/analyze",
        files={"file": ("test.png", buf, "image/png")},
    )
    assert resp.status_code == 400
    assert "template" in resp.json()["detail"].lower()


def test_demo_case_endpoint(client):
    """GET /demo-case should return demo data."""
    resp = client.get("/demo-case")
    assert resp.status_code == 200
    data = resp.json()
    assert "request" in data


def test_preprocess_vision_diff(client):
    """POST /preprocess/vision/diff-box should return a bbox or null."""
    resp = client.post("/preprocess/vision/diff-box", json={
        "design_image": {"mime_type": "image/png", "file_path": "data/assets/template_board.png"},
        "tested_image": {"mime_type": "image/png", "file_path": "data/assets/tested_board.png"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "heuristic_diff_bbox" in data


def test_single_photo_inspection_sends_whole_board_and_closeups(client):
    image = Image.new("RGB", (400, 240), (25, 90, 55))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    gemini = MagicMock()
    gemini.generate_json.return_value = {"summary": "Review complete.", "findings": []}
    engine = SimpleNamespace(gemini=gemini)

    with patch("app.main.get_engine", return_value=engine):
        response = client.post("/analysis/inspect-photo", json={
            "image": {
                "mime_type": "image/png",
                "base64_data": base64.b64encode(buf.getvalue()).decode("ascii"),
            },
        })

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "No defect was flagged by the model. This is an inconclusive review, not a pass."
    assert data["findings"][0]["severity"] == "uncertain"
    assert "cannot establish" in data["findings"][0]["visual_evidence"]
    call = gemini.generate_json.call_args.kwargs
    assert call["task_name"] == "Photo PCB Inspector"
    assert len(call["image_parts"]) == 5


def test_single_photo_inspection_prioritizes_and_surfaces_red_marked_area(client):
    from PIL import ImageDraw

    image = Image.new("RGB", (400, 240), (25, 90, 55))
    ImageDraw.Draw(image).ellipse((175, 85, 225, 135), outline=(255, 20, 10), width=7)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    gemini = MagicMock()
    gemini.generate_json.return_value = {"summary": "No issue seen.", "findings": []}
    engine = SimpleNamespace(gemini=gemini)

    with patch("app.main.get_engine", return_value=engine):
        response = client.post("/analysis/inspect-photo", json={
            "image": {
                "mime_type": "image/png",
                "base64_data": base64.b64encode(buf.getvalue()).decode("ascii"),
            },
        })

    assert response.status_code == 200
    data = response.json()
    assert data["findings"][0]["severity"] == "uncertain"
    assert "marked area" in data["findings"][0]["defect"].lower()
    assert len(gemini.generate_json.call_args.kwargs["image_parts"]) == 6
