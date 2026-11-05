from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

DEFAULT_BACKGROUND_CONTEXT = (
    "PCB Forge is a PCB hardware quality-inspection workspace. Diagnose a reported "
    "hardware symptom using the supplied error log, design/reference image, tested-board "
    "image, and specification evidence. Clearly separate visual evidence from hypotheses."
)
DEFAULT_TODO_CONTEXT = (
    "Prioritize traceable defect identification, specification compliance, likely root cause, "
    "and practical verification or repair actions. State uncertainty when the evidence is limited."
)
DEFAULT_EXAMPLE_CONTEXT = (
    "Treat the provided files as the source of truth. Return only schema-conformant results, "
    "cite concrete components or image regions when possible, and do not invent measurements."
)


def read_context_file(path: Path, fallback: str) -> str:
    """Read an optional prompt context file, using a built-in default if it is absent."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback


def parse_api_keys(raw: str | None) -> list[str]:
    if not raw:
        return []

    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]

    parts = [chunk.strip().strip('"\'') for chunk in text.split(",")]
    cleaned = [item for item in parts if item]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def is_probable_gemini_key(key: str) -> bool:
    return bool(re.match(r"^AIza[\w-]{20,}$", key))


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_api_keys: list[str]
    default_model: str | None
    default_temperature: float
    max_output_tokens: int
    request_timeout_sec: int
    context_background_path: Path
    context_todo_path: Path
    context_example_path: Path
    demo_case_path: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw_multi = (
        os.getenv("GEMINI_API_KEYS")
        or os.getenv("gemini_api_keys")
        or ""
    )
    parsed_multi = parse_api_keys(raw_multi)

    single_key = os.getenv("GEMINI_API_KEY") or None
    merged = parsed_multi[:]
    if single_key and single_key not in merged:
        merged.append(single_key)

    # Keep potentially invalid keys too; runtime probing handles true validity.
    return Settings(
        gemini_api_key=merged[0] if merged else None,
        gemini_api_keys=merged,
        default_model=os.getenv("DEFAULT_MODEL") or "gemini-3.8-flash",
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.2")),
        max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "1200")),
        request_timeout_sec=int(os.getenv("REQUEST_TIMEOUT_SEC", "45")),
        context_background_path=ROOT_DIR / "background.md",
        context_todo_path=ROOT_DIR / "todo.md",
        context_example_path=ROOT_DIR / "example.md",
        demo_case_path=ROOT_DIR / "data" / "demo_case.json",
    )
