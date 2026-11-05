"""Shared test fixtures for integration and unit tests."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.gemini_client import GeminiService
from app.schemas import GeminiDefectResponse, Severity


@pytest.fixture
def sample_png_bytes() -> bytes:
    """A small solid-color PNG for testing."""
    img = Image.new("RGB", (100, 100), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_gemini_service() -> GeminiService:
    """A mock GeminiService that won't make real API calls."""
    svc = MagicMock(spec=GeminiService)
    svc.classify_crop.return_value = GeminiDefectResponse(
        defect_type="short",
        description="Test defect",
        severity=Severity.HIGH,
    )
    svc.annotate_crop.return_value = None
    svc.key_pool_status.return_value = []
    return svc
