from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .gemini_client import GeminiService
from .orchestrator import OrchestrationEngine
from .routes import analysis, ecosystem, health, orchestration, preprocess

app = FastAPI(
    title="Gemini Agentic Orchestration Backend",
    version="0.1.0",
    description="Hackathon demo backend for multi-agent PCB validation with Gemini",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_assets_dir = Path(__file__).resolve().parent.parent / "data" / "assets"
if _assets_dir.is_dir():
    app.mount("/images", StaticFiles(directory=str(_assets_dir)), name="images")

# Register routers
app.include_router(health.router)
app.include_router(preprocess.router)
app.include_router(orchestration.router)
app.include_router(analysis.router)
app.include_router(ecosystem.router)


@app.on_event("startup")
def startup() -> None:
    settings = get_settings()
    app.state.settings = settings

    if not settings.gemini_api_keys:
        app.state.engine = None
        return

    gemini_service = GeminiService(
        api_keys=settings.gemini_api_keys,
        request_timeout_sec=settings.request_timeout_sec,
    )
    app.state.engine = OrchestrationEngine(
        settings=settings,
        gemini_service=gemini_service,
    )


def get_engine() -> OrchestrationEngine:
    engine = getattr(app.state, "engine", None)
    if not engine:
        raise HTTPException(
            status_code=503,
            detail="No Gemini API keys configured. Set GEMINI_API_KEYS (or gemini_api_keys) in .env.",
        )
    return engine
