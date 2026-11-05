"""PCB Agent: wraps the PCB parsing tool and emits agent timeline events."""
from tools.pcb_parser import analyze_pcb_file
from models import PCBAnalysis
import db
from datetime import datetime
import uuid


def run(project_id: str, file_path: str) -> PCBAnalysis:
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "PCB Agent",
        "icon": "🤖", "message": "Analyzing PCB...", "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    })
    data = analyze_pcb_file(file_path)
    analysis = PCBAnalysis(**data)
    db.add_event(project_id, {
        "id": str(uuid.uuid4()), "project_id": project_id, "agent": "PCB Agent",
        "icon": "\u2705", "message": f"PCB analysis completed ({analysis.source})", "status": "done",
        "timestamp": datetime.utcnow().isoformat(),
    })
    return analysis
