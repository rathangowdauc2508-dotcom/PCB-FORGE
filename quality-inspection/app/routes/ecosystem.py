from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ecosystem", tags=["pcb-ecosystem"])


class BuildPlanRequest(BaseModel):
    model: str | None = None
    project_id: str = Field(min_length=1, max_length=80)
    pcb_analysis: dict
    dfm_result: dict
    bom_result: dict
    manufacturing_recommendation: dict
    physical_inspection: dict


class ManufacturingSummaryRequest(BaseModel):
    kind: Literal["dfm", "bom", "recommendation"]
    facts: dict
    model: str | None = None


BUILD_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "manufacturing_readiness": {"type": "string", "enum": ["READY", "READY_WITH_ACTIONS", "HOLD"]},
        "design_risks": {"type": "array", "items": {"type": "string"}},
        "quality_findings": {"type": "array", "items": {"type": "string"}},
        "recommended_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "reason": {"type": "string"},
                },
                "required": ["action", "priority", "reason"],
            },
        },
        "prototype_checklist": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": [
        "executive_summary", "manufacturing_readiness", "design_risks",
        "quality_findings", "recommended_actions", "prototype_checklist", "confidence",
    ],
}


def _get_engine():
    from ..main import get_engine
    return get_engine()


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "evidence_refs"],
}


def _build_evidence_index(kind: str, facts: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if kind == "dfm":
        rows.append({"id": "DFM-STATUS", "label": "DFM status", "detail": f"{facts.get('status')} · {facts.get('passed_checks')}/{facts.get('total_checks')} checks passed"})
        for index, check in enumerate(facts.get("checks", []), start=1):
            rows.append({"id": f"DFM-C{index:02d}", "label": check.get("name", "DFM check"), "detail": "Passed" if check.get("passed") else "Failed"})
        for index, issue in enumerate(facts.get("issues", []), start=1):
            rows.append({"id": f"DFM-I{index:02d}", "label": issue.get("type", "DFM issue").replace("_", " "), "detail": issue.get("message", "")})
    elif kind == "bom":
        rows.append({"id": "BOM-COST", "label": "Estimated BOM cost", "detail": f"${facts.get('total_cost_usd')} per unit; planning estimate"})
        rows.append({"id": "BOM-RISK", "label": "Sourcing risk count", "detail": f"{facts.get('risk_count')} items with sourcing risk"})
        for index, item in enumerate(facts.get("items", []), start=1):
            rows.append({"id": f"BOM-{index:02d}", "label": item.get("part", "BOM item"), "detail": f"Quantity {item.get('quantity')}; {item.get('availability')}; {item.get('description', '')}"})
    else:
        rows.append({"id": "MFR-RECOMMENDATION", "label": "Recommended supplier", "detail": json.dumps(facts.get("recommended", {}), ensure_ascii=False)})
        for index, quote in enumerate(facts.get("all_quotes", []), start=1):
            rows.append({"id": f"MFR-{index:02d}", "label": quote.get("manufacturer_name", "Supplier quote"), "detail": f"${quote.get('price_usd')}; {quote.get('lead_time_days')} days; score {quote.get('score')}; compatible={quote.get('dfm_compatible')}"})
    return rows


@router.post("/manufacturing-summary")
def manufacturing_summary(payload: ManufacturingSummaryRequest) -> dict:
    """Give deterministic manufacturing evidence to Gemma 4 for a concise interpretation."""
    engine = _get_engine()
    try:
        model = engine._pick_model(payload.model)
        if not model.startswith("gemma-4"):
            raise ValueError("PCB Forge manufacturing insights are restricted to Gemma 4 models.")

        role, task = {
            "dfm": (
                "PCB design-for-manufacturing engineer",
                "Explain the deterministic DFM status, prioritize any failed or risky checks, and give the next practical action. Do not change the reported measurements or pass/fail results.",
            ),
            "bom": (
                "PCB component sourcing analyst",
                "Explain component availability and substitution risks, summarize the supplied cost, and give practical sourcing actions. Do not invent stock, prices, or alternatives.",
            ),
            "recommendation": (
                "PCB fabrication sourcing analyst",
                "Explain why the deterministic supplier recommendation ranks highest, using only the supplied quotes, compatibility, prices, lead times, and scores.",
            ),
        }[payload.kind]
        evidence_index = _build_evidence_index(payload.kind, payload.facts)
        evidence_ids = {row["id"] for row in evidence_index}
        if not evidence_index:
            raise ValueError("No evidence was available to review.")
        prompt = (
            f"You are a {role} for PCB Forge. {task} "
            "Use only the facts below. Be concise, specific, and clear about uncertainty. "
            "Cite the exact evidence IDs that support your explanation in evidence_refs. "
            "Use IDs from the supplied evidence index only; do not create IDs. "
            "Return one short paragraph and at least one evidence reference in the required JSON schema.\n\n"
            "Facts (JSON):\n" + json.dumps(payload.facts, ensure_ascii=False)
            + "\n\nEvidence index (JSON):\n" + json.dumps(evidence_index, ensure_ascii=False)
        )
        result = engine.gemini.generate_json(
            model=model,
            prompt=prompt,
            response_schema=SUMMARY_SCHEMA,
            temperature=0.15,
            max_output_tokens=500,
        )
        refs = result.get("evidence_refs", [])
        if not isinstance(refs, list):
            raise RuntimeError("Gemma 4 returned invalid evidence references.")
        valid_refs = list(dict.fromkeys(ref for ref in refs if ref in evidence_ids))
        if not valid_refs and evidence_index:
            raise RuntimeError("Gemma 4 did not cite a valid evidence ID.")
        return {
            "summary": result["summary"],
            "model_used": model,
            "evidence": [row for row in evidence_index if row["id"] in valid_refs],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemma 4 {payload.kind} summary failed: {exc}") from exc


@router.post("/build-plan")
def build_plan(payload: BuildPlanRequest) -> dict:
    engine = _get_engine()
    try:
        model = engine._pick_model(payload.model)
        if not model.startswith("gemma-4"):
            raise ValueError("The ecosystem build planner is restricted to Gemma 4 models.")
        facts = payload.model_dump(exclude={"model"})
        prompt = (
            "You are PCB Forge's PCB ecosystem build-planning agent. Use only the supplied evidence. "
            "Combine the KiCad geometry, deterministic DFM checks, BOM sourcing risks, supplier compatibility, "
            "and Gemma vision inspection. Do not invent measurements, component facts, or factory capabilities. "
            "If the board has a high-severity DFM failure or physical defect, readiness must be HOLD. "
            "If uncertainty remains, call it out and request a human check. Treat the supplier catalogue as a planning estimate. "
            "Return practical actions ordered by priority and a concise prototype checklist.\n\n"
            "PCB project evidence (JSON):\n" + json.dumps(facts, ensure_ascii=False)
        )
        advice = engine.gemini.generate_json(
            model=model,
            prompt=prompt,
            response_schema=BUILD_PLAN_SCHEMA,
            temperature=0.15,
            max_output_tokens=1400,
        )
        return {"project_id": payload.project_id, "model_used": model, "build_plan": advice}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemma 4 build planning failed: {exc}") from exc
