from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from .schemas import ImageInput


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_image_bytes(image: ImageInput, root_dir: Path) -> bytes:
    if image.base64_data:
        return base64.b64decode(image.base64_data)

    if image.file_path:
        file_path = Path(image.file_path)
        if not file_path.is_absolute():
            file_path = (root_dir / file_path).resolve()
        return file_path.read_bytes()

    raise ValueError("Image source is missing")


def safe_json_loads(payload: str) -> dict[str, Any]:
    try:
        loaded = json.loads(payload)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", payload):
        try:
            loaded, _ = decoder.raw_decode(payload[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("Model output did not contain a valid JSON object")


def truncate_text(text: str, max_len: int = 5000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...[truncated]"
