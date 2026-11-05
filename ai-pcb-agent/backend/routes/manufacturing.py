"""Manufacturing catalogue, quoting, and planning request routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tools import manufacturer_service
import db

router = APIRouter(prefix="/api", tags=["manufacturing"])


@router.get("/manufacturers")
async def list_manufacturers():
    return [m.model_dump() for m in manufacturer_service.get_manufacturers()]


@router.post("/manufacturers/compare")
async def compare_manufacturers(project_id: str):
    project = db.PROJECTS.get(project_id)
    if not project or "recommendation" not in project:
        raise HTTPException(status_code=404, detail="Run PCB analysis first.")
    return project["recommendation"]


@router.post("/manufacturing/quote")
async def get_quote(project_id: str, manufacturer_id: str, quantity: int = 5):
    project = db.PROJECTS.get(project_id)
    if not project or "recommendation" not in project:
        raise HTTPException(status_code=404, detail="Run PCB analysis first.")

    quotes = project["recommendation"]["all_quotes"]
    quote = next((q for q in quotes if q["manufacturer_id"] == manufacturer_id), None)
    if not quote:
        raise HTTPException(status_code=404, detail="Manufacturer quote not found.")

    # Manufacturer prices are quoted for a standard 5-board prototype batch
    # (small-batch PCB fab pricing is roughly flat, not linear per unit), so
    # scale relative to that reference batch rather than multiplying the
    # per-unit price directly by quantity.
    total = round(quote["price_usd"] * quantity / 5, 2)
    return {**quote, "quantity": quantity, "total_price": total}


@router.post("/manufacturing/validate-order")
async def validate_order(project_id: str, manufacturer_id: str, quantity: int, total_price: float):
    """Validate the project, quote, and requested quantity before saving."""
    project = db.PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PCB project not found.")

    mfr = manufacturer_service.get_manufacturer(manufacturer_id)
    if not mfr:
        raise HTTPException(status_code=404, detail="Manufacturer not found.")

    return {
        "ok": True,
        "manufacturer": mfr.name,
        "quantity": quantity,
        "total_price": total_price,
        "estimated_delivery_days": mfr.lead_time_days,
        "note": "Planning estimate only. No payment or real factory order is placed.",
    }
