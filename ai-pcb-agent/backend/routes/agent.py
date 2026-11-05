from __future__ import annotations

from fastapi import APIRouter, HTTPException
import db

router = APIRouter(prefix="/api", tags=["agent"])


def _normalize(events: list[dict]) -> list[dict]:
    """Close out 'running' events that have already been superseded.

    Agents emit a "running" event and then a SEPARATE "done" event rather than
    updating the first one. Left as-is, every "running" row spins forever in
    the UI and the pipeline looks stuck long after it finished.

    A "running" event is finished if a later event exists from the same agent,
    or if the orchestrator has reported the pipeline complete. Doing this
    server-side means the timeline is correct regardless of which build of the
    frontend is loaded.
    """
    if not events:
        return events

    last_index_by_agent: dict[str, int] = {}
    for i, e in enumerate(events):
        last_index_by_agent[e.get("agent", "")] = i

    pipeline_done = any(
        e.get("status") == "done"
        and any(k in (e.get("message") or "").lower() for k in ("complete", "confirmed", "approval"))
        for e in events
    )

    out = []
    for i, e in enumerate(events):
        e = dict(e)
        if e.get("status") == "running":
            superseded = pipeline_done or last_index_by_agent.get(e.get("agent", ""), i) > i
            if superseded:
                e["status"] = "done"
                e["superseded"] = True
        out.append(e)
    return out


@router.get("/agent/events/{project_id}")
async def get_events(project_id: str):
    if project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="Project not found.")
    return _normalize(db.get_events(project_id))
