from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..schemas import KeyPoolStatusResponse, ModelsResponse

router = APIRouter(tags=["health"])


def _get_engine():
    """Import lazily to avoid circular imports."""
    from ..main import get_engine
    return get_engine()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "time_utc": datetime.now(tz=UTC).isoformat(),
        "gemini_api_key_configured": bool(settings.gemini_api_keys),
        "gemini_key_count": len(settings.gemini_api_keys),
    }


@router.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    engine = _get_engine()
    try:
        available = engine.list_models()
        recommended = engine.gemini.pick_recommended_model(
            available,
            default_model=engine.settings.default_model,
        )
        return ModelsResponse(recommended_model=recommended, available_models=available)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Gemini models: {exc}") from exc


@router.get("/keys/status", response_model=KeyPoolStatusResponse)
def key_pool_status() -> KeyPoolStatusResponse:
    engine = _get_engine()
    status = engine.gemini.key_pool_status()
    return KeyPoolStatusResponse(key_count=len(status), keys=status)
