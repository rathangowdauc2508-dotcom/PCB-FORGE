"""Manufacturing Agent: gets quotes from all manufacturers (each evaluated
against their OWN capability limits via the DFM engine), compares them, and
produces an explainable recommendation."""
from tools import manufacturer_service, llm_service
from tools.dfm_checker import run_dfm_checks
from models import PCBAnalysis, ManufacturingRecommendation
import db
from datetime import datetime
import uuid


def run(project_id: str, pcb: PCBAnalysis) -> ManufacturingRecommendation:
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "Manufacturing Agent",
        "icon": "\U0001F3ED", "message": "Comparing manufacturers...", "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    })

    manufacturers = manufacturer_service.get_manufacturers()
    dfm_by_mfr = {m.id: run_dfm_checks(pcb, m) for m in manufacturers}
    quotes = manufacturer_service.get_quotes(pcb, dfm_by_mfr)

    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "Manufacturing Agent",
        "icon": "\u2705", "message": f"{len(quotes)} manufacturers evaluated", "status": "done",
        "timestamp": datetime.utcnow().isoformat(),
    })

    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "Decision Agent",
        "icon": "\U0001F9E0", "message": "Selecting optimal manufacturer...", "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    })
    recommendation = manufacturer_service.recommend(quotes)
    try:
        recommendation.explanation = llm_service.explain_recommendation(recommendation)
        recommendation.ai_status = "available"
    except RuntimeError:
        recommendation.ai_status = "unavailable"
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "Decision Agent",
        "icon": "\u2705", "message": f"{recommendation.recommended.manufacturer_name} selected", "status": "done",
        "timestamp": datetime.utcnow().isoformat(),
    })
    return recommendation
