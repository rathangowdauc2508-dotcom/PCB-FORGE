from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_BACKGROUND_CONTEXT,
    DEFAULT_EXAMPLE_CONTEXT,
    DEFAULT_TODO_CONTEXT,
    Settings,
    read_context_file,
)
from .schemas import DemoCaseResponse, OrchestrationRequest


def load_demo_case(settings: Settings) -> DemoCaseResponse:
    payload: dict[str, Any] = json.loads(settings.demo_case_path.read_text(encoding="utf-8"))

    request_payload = payload["request"]
    request_payload["input"].setdefault(
        "background_context",
        read_context_file(settings.context_background_path, DEFAULT_BACKGROUND_CONTEXT),
    )
    request_payload["input"].setdefault(
        "todo_context",
        read_context_file(settings.context_todo_path, DEFAULT_TODO_CONTEXT),
    )
    request_payload["input"].setdefault(
        "example_context",
        read_context_file(settings.context_example_path, DEFAULT_EXAMPLE_CONTEXT),
    )

    # Keep demo paths relative to the repository root for portability.
    root = Path(__file__).resolve().parents[1]
    for key in ("design_image", "tested_image"):
        source = request_payload["input"][key]
        if source.get("file_path"):
            relative = Path(source["file_path"])
            if relative.is_absolute():
                source["file_path"] = str(relative.relative_to(root))

    return DemoCaseResponse(
        request=OrchestrationRequest.model_validate(request_payload),
        expected_output_example=payload["expected_output_example"],
    )
