"""Gemma 4 interpretation layer for deterministic PCB manufacturing results."""
from __future__ import annotations

import os
from typing import Any

import httpx


GEMMA_API_URL = os.getenv("GEMMA_API_URL", "http://localhost:8001").rstrip("/")
GEMMA_MODEL = os.getenv("GEMMA_MODEL") or None


def _plain_facts(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _complete(kind: str, facts: Any) -> tuple[str, list[dict[str, str]]]:
    """Ask the shared inspection service's configured Gemma 4 model for an evidence-based summary."""
    try:
        response = httpx.post(
            f"{GEMMA_API_URL}/ecosystem/manufacturing-summary",
            json={"kind": kind, "facts": _plain_facts(facts), "model": GEMMA_MODEL},
            timeout=120.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(
            "Gemma 4 service is unreachable. Start the quality-inspection API on port 8001."
        ) from exc

    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        raise RuntimeError(f"Gemma 4 {kind} review failed ({response.status_code}): {detail}")

    try:
        payload = response.json()
        summary = payload["summary"].strip()
        model = payload["model_used"]
        evidence = payload["evidence"]
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        raise RuntimeError("Gemma 4 service returned an invalid summary response.") from exc

    if not summary or not model.startswith("gemma-4"):
        raise RuntimeError("Gemma 4 service did not return a valid Gemma 4 summary.")
    if not isinstance(evidence, list) or any(not isinstance(row, dict) or not row.get("id") for row in evidence):
        raise RuntimeError("Gemma 4 service returned invalid evidence references.")
    return summary, evidence


def summarize_dfm(dfm_result) -> tuple[str, list[dict[str, str]]]:
    facts = _plain_facts(dfm_result)
    return _complete("dfm", facts)


def summarize_bom(bom_result) -> tuple[str, list[dict[str, str]]]:
    facts = _plain_facts(bom_result)
    return _complete("bom", facts)


def explain_recommendation(recommendation) -> str:
    summary, _evidence = _complete("recommendation", _plain_facts(recommendation))
    return summary
