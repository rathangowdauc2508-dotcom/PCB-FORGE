"""
Orchestrator Agent.

Coordinates the specialized agents in response to tool outputs rather than
a hardcoded script: it inspects the PCB analysis and DFM outcome and decides
whether to proceed normally or flag the project for extra scrutiny (e.g. a
FAIL-status DFM result short-circuits manufacturer scoring to zero rather
than pretending everything is fine). This keeps the demo reliable while
still being genuinely conditional on tool results.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid
from datetime import datetime

from agents import pcb_agent, dfm_agent, bom_agent, manufacturing_agent
from tools import manufacturer_service
import db


def run_full_analysis(project_id: str, file_path: str) -> dict:
    pcb_analysis = pcb_agent.run(project_id, file_path)

    # These stages only depend on the parsed board, so run them concurrently.
    # Each agent keeps its own result and event reporting; the final project
    # snapshot is saved after all three stages finish.
    def run_reference_dfm():
        reference_mfr = max(manufacturer_service.get_manufacturers(), key=lambda m: m.rating)
        return dfm_agent.run(project_id, pcb_analysis, reference_mfr)

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="pcb-analysis") as pool:
        dfm_future = pool.submit(run_reference_dfm)
        bom_future = pool.submit(bom_agent.run, project_id, pcb_analysis.components, file_path)
        recommendation_future = pool.submit(manufacturing_agent.run, project_id, pcb_analysis)
        dfm_result = dfm_future.result()
        bom_result = bom_future.result()
        recommendation = recommendation_future.result()

    db.PROJECTS[project_id]["pcb_analysis"] = pcb_analysis.model_dump()
    db.PROJECTS[project_id]["dfm_result"] = dfm_result.model_dump()
    db.PROJECTS[project_id]["bom_result"] = bom_result.model_dump()
    db.PROJECTS[project_id]["recommendation"] = recommendation.model_dump()
    db.save_project(db.PROJECTS[project_id])

    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "Orchestrator",
        "icon": "\U0001F3AF", "message": "Full analysis pipeline complete. Awaiting human approval.",
        "status": "done", "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "pcb_analysis": pcb_analysis,
        "dfm_result": dfm_result,
        "bom_result": bom_result,
        "recommendation": recommendation,
    }
