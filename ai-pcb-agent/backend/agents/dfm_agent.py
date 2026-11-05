"""DFM Agent: wraps the deterministic DFM rule engine and adds AI explanation."""
from tools.dfm_checker import run_dfm_checks
from tools import llm_service
from models import PCBAnalysis, Manufacturer, DFMResult
import db
from datetime import datetime
import uuid


def run(project_id: str, pcb: PCBAnalysis, manufacturer: Manufacturer) -> DFMResult:
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "DFM Agent",
        "icon": "\U0001F527", "message": "Running deterministic DFM checks and optional AI explanation...", "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    })
    result = run_dfm_checks(pcb, manufacturer)
    try:
        result.ai_summary, result.ai_evidence = llm_service.summarize_dfm(result)
        result.ai_status = "available"
        completion = "DFM checks and AI explanation completed"
    except RuntimeError:
        result.ai_status = "unavailable"
        completion = "DFM checks completed; optional AI explanation was unavailable"
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "DFM Agent",
        "icon": "\u2705", "message": f"{completion}: {result.passed_checks}/{result.total_checks} checks passed",
        "status": "done", "timestamp": datetime.utcnow().isoformat(),
    })
    return result
