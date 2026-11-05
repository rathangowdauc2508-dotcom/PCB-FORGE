from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.gemini_client import GeminiService


def build_candidates(model_names: list[str]) -> list[str]:
    priority = [
        "gemini-3.1-pro-preview-customtools",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-3-pro-image-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-pro-latest",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]
    available = set(model_names)
    return [name for name in priority if name in available]


def main() -> None:
    settings = get_settings()
    if not settings.gemini_api_keys:
        raise SystemExit("No API keys configured. Set GEMINI_API_KEYS or gemini_api_keys in .env")

    service = GeminiService(api_keys=settings.gemini_api_keys, request_timeout_sec=settings.request_timeout_sec)
    available = service.list_generate_models()
    candidate_models = build_candidates([m.name for m in available])

    image_path = Path("data/assets/tested_board.png")
    image_bytes = image_path.read_bytes()

    results = service.probe_vision_models(
        candidate_models=candidate_models,
        image_bytes=image_bytes,
        mime_type="image/png",
    )

    now = datetime.now(tz=UTC)
    callable_models = [row["model"] for row in results if row.get("vision_callable")]

    payload = {
        "probed_at_utc": now.isoformat(),
        "date": now.date().isoformat(),
        "configured_key_count": len(settings.gemini_api_keys),
        "available_generate_models": [m.name for m in available],
        "candidate_models": candidate_models,
        "vision_callable_models": callable_models,
        "results": results,
        "key_pool_status": service.key_pool_status(),
    }

    out_path = Path("data/model_probe_latest.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out_path}")
    print(f"Vision-callable models: {len(callable_models)}")
    for name in callable_models:
        print(f"- {name}")


if __name__ == "__main__":
    main()
