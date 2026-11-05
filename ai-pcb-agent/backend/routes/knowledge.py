from __future__ import annotations

import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

import db
import knowledge
import os
import httpx

router = APIRouter(prefix="/api/knowledge", tags=["engineering-knowledge"])


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    project_id: str | None = Field(default=None, max_length=80)
    revision_id: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=6, ge=1, le=12)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    project_id: str | None = Query(default=None, max_length=80),
    revision_id: str | None = Query(default=None, max_length=80),
):
    if project_id and project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    if revision_id:
        revision = db.get_board_revision(revision_id)
        if not revision or revision["project_id"] != project_id:
            raise HTTPException(status_code=404, detail="PCB revision not found in this project.")
    filename = Path((file.filename or "").replace("\\", "/")).name
    if not filename or Path(filename).suffix.lower() not in knowledge.ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Upload a PDF, TXT, or Markdown document.")
    temp_path = knowledge.DOCUMENT_DIR / f".upload-{uuid.uuid4().hex}.tmp"
    size = 0
    try:
        knowledge.DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
        with temp_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > knowledge.MAX_DOCUMENT_BYTES:
                    raise HTTPException(status_code=413, detail="Document exceeds the configured upload limit.")
                output.write(chunk)
        if not size:
            raise HTTPException(status_code=400, detail="The uploaded document is empty.")
        try:
            result = knowledge.ingest(temp_path, filename, project_id, revision_id)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Could not extract this document. Check that the file is valid and readable.") from exc
        return {**result, "duplicate": result.get("duplicate", False)}
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/documents")
def get_documents(
    project_id: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if project_id and project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    return {"items": knowledge.list_documents(project_id, limit, offset), "limit": limit, "offset": offset}


@router.get("/documents/{document_id}")
def get_document(document_id: str):
    result = knowledge.get_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return result


@router.delete("/documents/{document_id}")
def remove_document(document_id: str):
    if not knowledge.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return {"deleted": True, "id": document_id}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str):
    document = knowledge.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    with knowledge._connection() as source:
        row = source.execute("SELECT storage_path, filename, project_id, revision_id FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
    try:
        result = knowledge.ingest(Path(row["storage_path"]), row["filename"], row["project_id"], row["revision_id"], force=True)
        return {**result, "duplicate": False}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Reindex failed: {str(exc)[:300]}") from exc


@router.post("/query")
def query_knowledge(payload: QueryRequest):
    if payload.project_id and payload.project_id not in db.PROJECTS:
        raise HTTPException(status_code=404, detail="PCB project not found.")
    if payload.revision_id:
        revision = db.get_board_revision(payload.revision_id)
        if not revision or revision["project_id"] != payload.project_id:
            raise HTTPException(status_code=404, detail="PCB revision not found in the selected project.")
    evidence = knowledge.retrieve(payload.question, payload.project_id, payload.revision_id, payload.top_k)
    result = knowledge.answer(payload.question, evidence)
    if not result["abstained"] and evidence:
        base = os.getenv("GEMMA_API_URL", "http://localhost:8001").rstrip("/")
        try:
            response = httpx.post(
                f"{base}/ecosystem/knowledge-answer",
                json={"question": payload.question, "evidence": evidence},
                timeout=float(os.getenv("KNOWLEDGE_LLM_TIMEOUT", "20")),
            )
            if response.is_success:
                generated = response.json()
                valid_ids = {str(item.get("id")) for item in evidence}
                citations = [item for item in generated.get("citation_ids", []) if item in valid_ids]
                if generated.get("answer") and citations:
                    chosen = [item for item in evidence if item.get("id") in citations]
                    result = {"answer": generated["answer"], "abstained": False,
                              "sources": chosen, "model_status": "gemma-4",
                              "model_used": generated.get("model_used")}
        except (httpx.HTTPError, ValueError, TypeError):
            pass
    return {
        **result,
        "question": payload.question,
        "project_id": payload.project_id,
        "revision_id": payload.revision_id,
        "source_count": len(result["sources"]),
    }