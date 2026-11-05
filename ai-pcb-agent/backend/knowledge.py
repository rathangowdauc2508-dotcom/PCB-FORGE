"""Document ingestion and evidence retrieval for PCB Forge knowledge RAG."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import db

DATA_DIR = Path(__file__).parent / "data"
DOCUMENT_DIR = DATA_DIR / "knowledge"
MAX_DOCUMENT_BYTES = int(os.getenv("KNOWLEDGE_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
EMBEDDING_MODEL = os.getenv("KNOWLEDGE_EMBEDDING_MODEL", "gemini-embedding-001")
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}
ABSTENTION = "I couldn't find sufficient evidence in the selected project's indexed documents or records to answer this reliably."


@contextmanager
def _connection():
    conn = sqlite3.connect(db.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    with _connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge_documents (
          id TEXT PRIMARY KEY, project_id TEXT, revision_id TEXT, filename TEXT NOT NULL,
          storage_path TEXT NOT NULL, content_hash TEXT NOT NULL, byte_size INTEGER NOT NULL,
          source_type TEXT NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL,
          indexed_at TEXT, document_version INTEGER NOT NULL DEFAULT 1, is_active INTEGER NOT NULL DEFAULT 1,
          UNIQUE(project_id, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_documents_scope
          ON knowledge_documents(project_id, revision_id, status);
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
          id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
          project_id TEXT, revision_id TEXT, ordinal INTEGER NOT NULL, page_number INTEGER,
          section_title TEXT, content TEXT NOT NULL, created_at TEXT NOT NULL,
          embedding_json TEXT, embedding_model TEXT,
          UNIQUE(document_id, ordinal)
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_scope
          ON knowledge_chunks(project_id, revision_id, document_id);
        """)
        doc_columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_documents)").fetchall()}
        if "document_version" not in doc_columns:
            conn.execute("ALTER TABLE knowledge_documents ADD COLUMN document_version INTEGER NOT NULL DEFAULT 1")
        if "is_active" not in doc_columns:
            conn.execute("ALTER TABLE knowledge_documents ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_chunks)").fetchall()}
        if "embedding_json" not in columns:
            conn.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_json TEXT")
        if "embedding_model" not in columns:
            conn.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_model TEXT")


def _extract(path: Path) -> list[tuple[int | None, str]]:
    if path.suffix.lower() in {".txt", ".md"}:
        return [(None, path.read_text(encoding="utf-8-sig"))]
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support needs the backend dependency pypdf. Install backend requirements and retry.") from exc
    reader = PdfReader(str(path), strict=True)
    pages = [(index + 1, (page.extract_text() or "").strip()) for index, page in enumerate(reader.pages)]
    if not any(text for _, text in pages):
        raise ValueError("This PDF has no extractable text. Scanned PDFs need OCR, which is not enabled.")
    return pages


def _heading(text: str) -> str | None:
    match = re.search(r"(?m)^#{1,6}\s+(.+)$", text)
    return match.group(1).strip()[:200] if match else None


def _chunks(pages: list[tuple[int | None, str]], target: int = 1200, overlap: int = 180) -> list[dict]:
    result = []
    for page, text in pages:
        blocks = re.split(r"\n\s*\n|(?=^#{1,6}\s)", text, flags=re.MULTILINE)
        current = ""
        for block in blocks:
            block = re.sub(r"[ \t]+", " ", block).strip()
            if not block:
                continue
            if len(current) + len(block) + 2 <= target:
                current = f"{current}\n\n{block}".strip()
            else:
                if current:
                    result.append({"page_number": page, "section_title": _heading(current), "content": current})
                current = f"{current[-overlap:] if overlap else ''}\n{block}".strip()
                while len(current) > target * 1.5:
                    result.append({"page_number": page, "section_title": _heading(current[:target]), "content": current[:target]})
                    current = current[target - overlap:]
        if current:
            result.append({"page_number": page, "section_title": _heading(current), "content": current})
    return result


def _request_embeddings(texts: list[str]) -> list[list[float]] | None:
    base = os.getenv("GEMMA_API_URL", "http://localhost:8001").rstrip("/")
    vectors: list[list[float]] = []
    try:
        for start in range(0, len(texts), 24):
            response = httpx.post(
                f"{base}/ecosystem/knowledge-embeddings",
                json={"texts": texts[start:start + 24], "model": EMBEDDING_MODEL},
                timeout=float(os.getenv("KNOWLEDGE_EMBEDDING_TIMEOUT", "10")),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("model") != EMBEDDING_MODEL:
                return None
            vectors.extend(payload.get("vectors", []))
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            return None
        return vectors
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def ingest(path: Path, filename: str, project_id: str | None, revision_id: str | None, force: bool = False) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Supported engineering documents: PDF, TXT, and Markdown.")
    size = path.stat().st_size
    if size <= 0 or size > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Document must be between 1 byte and {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB.")
    raw = path.read_bytes()
    if suffix == ".pdf" and raw[:5] != b"%PDF-":
        raise ValueError("The uploaded file does not have a valid PDF signature.")
    if suffix in {".txt", ".md"} and b"\x00" in raw[:4096]:
        raise ValueError("The uploaded text file contains binary data.")
    digest = hashlib.sha256(raw).hexdigest()
    with _connection() as conn:
        existing = conn.execute(
            "SELECT * FROM knowledge_documents WHERE project_id IS ? AND content_hash=?",
            (project_id, digest),
        ).fetchone()
    if existing and existing["status"] in {"indexed", "indexed_lexical"} and not force:
        path.unlink(missing_ok=True)
        return {**(get_document(existing["id"]) or _public(existing)), "duplicate": True}
    if existing:
        document_id = existing["id"]
        stored_path = Path(existing["storage_path"])
    else:
        document_id = "DOC-" + uuid.uuid4().hex[:12].upper()
        stored_path = DOCUMENT_DIR / f"{document_id}{suffix}"
        try:
            with path.open("rb") as source, stored_path.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
        path.unlink(missing_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        with _connection() as conn:
            version_row = conn.execute(
                "SELECT COALESCE(MAX(document_version), 0) + 1 FROM knowledge_documents WHERE project_id IS ? AND filename=?",
                (project_id, Path(filename).name),
            ).fetchone()
            document_version = int(version_row[0])
            conn.execute(
                "UPDATE knowledge_documents SET is_active=0 WHERE project_id IS ? AND filename=?",
                (project_id, Path(filename).name),
            )
            conn.execute(
                """INSERT INTO knowledge_documents
                (id, project_id, revision_id, filename, storage_path, content_hash, byte_size,
                 source_type, status, created_at, document_version, is_active)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?, 1)""",
                (document_id, project_id, revision_id, Path(filename).name, str(stored_path), digest, size,
                 "project_document" if project_id else "shared_document", now, document_version),
            )
    try:
        sections = _chunks(_extract(stored_path))
        if not sections:
            raise ValueError("No readable text was found in this document.")
        now = datetime.now(timezone.utc).isoformat()
        with _connection() as conn:
            conn.execute("DELETE FROM knowledge_chunks WHERE document_id=?", (document_id,))
            conn.executemany(
                """INSERT INTO knowledge_chunks
                (id, document_id, project_id, revision_id, ordinal, page_number, section_title, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [("CHK-" + uuid.uuid4().hex[:12].upper(), document_id, project_id, revision_id, index,
                  row["page_number"], row["section_title"], row["content"], now)
                 for index, row in enumerate(sections, start=1)],
            )
        vectors = _request_embeddings([row["content"] for row in sections])
        with _connection() as conn:
            if vectors and len(vectors) == len(sections):
                conn.executemany(
                    "UPDATE knowledge_chunks SET embedding_json=?, embedding_model=? WHERE document_id=? AND ordinal=?",
                    [(json.dumps(vector), EMBEDDING_MODEL, document_id, index) for index, vector in enumerate(vectors, start=1)],
                )
                status = "indexed"
            else:
                status = "indexed_lexical"
            conn.execute("UPDATE knowledge_documents SET status=?, error=NULL, indexed_at=? WHERE id=?", (status, now, document_id))
    except Exception as exc:
        with _connection() as conn:
            conn.execute("DELETE FROM knowledge_chunks WHERE document_id=?", (document_id,))
            conn.execute("UPDATE knowledge_documents SET status='failed', error=? WHERE id=?", (str(exc)[:500], document_id))
        raise
    return get_document(document_id) or {}


def _public(row: sqlite3.Row | dict) -> dict:
    data = dict(row)
    data.pop("storage_path", None)
    return data


def get_document(document_id: str) -> dict | None:
    with _connection() as conn:
        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
    return _public(row) if row else None


def list_documents(project_id: str | None, limit: int, offset: int) -> list[dict]:
    with _connection() as conn:
        rows = conn.execute(
            """SELECT id, project_id, revision_id, filename, content_hash, byte_size,
               source_type, status, error, created_at, indexed_at
               FROM knowledge_documents WHERE project_id IS NULL OR project_id IS ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (project_id, limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_document(document_id: str) -> bool:
    with _connection() as conn:
        row = conn.execute("SELECT storage_path FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM knowledge_documents WHERE id=?", (document_id,))
    Path(row["storage_path"]).unlink(missing_ok=True)
    return True


def _tokens(text: str) -> list[str]:
    return [value.lower() for value in re.findall(r"[A-Za-z0-9_./+-]+", text) if len(value) > 1][:24]


def _scoped_chunks(project_id: str | None, revision_id: str | None) -> tuple[str, list]:
    clauses = ["d.is_active=1", "d.status IN ('indexed', 'indexed_lexical')"]
    params: list = []
    if project_id:
        clauses.append("(c.project_id IS NULL OR c.project_id=?)")
        params.append(project_id)
    else:
        clauses.append("c.project_id IS NULL")
    if revision_id:
        clauses.append("(c.revision_id IS NULL OR c.revision_id=?)")
        params.append(revision_id)
    return " AND ".join(clauses), params


def retrieve(question: str, project_id: str | None, revision_id: str | None, limit: int = 8) -> list[dict]:
    tokens = _tokens(question)
    scope, scope_params = _scoped_chunks(project_id, revision_id)
    evidence_by_id: dict[str, dict] = {}
    if tokens:
        terms = " OR ".join("LOWER(c.content) LIKE ?" for _ in tokens)
        with _connection() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.filename AS source_title, d.source_type, d.content_hash
                    FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
                    WHERE {scope} AND ({terms}) ORDER BY c.ordinal LIMIT ?""",
                [*scope_params, *(f"%{token}%" for token in tokens), max(40, limit * 8)],
            ).fetchall()
        for row in rows:
            item = dict(row)
            item["kind"] = "document"
            item["relevance"] = sum(1 for token in tokens if token in item["content"].lower()) / len(tokens)
            evidence_by_id[item["id"]] = item

    with _connection() as conn:
        has_scoped_embeddings = conn.execute(
            f"""SELECT 1 FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id=c.document_id
                WHERE {scope} AND c.embedding_json IS NOT NULL AND c.embedding_model=?
                LIMIT 1""",
            [*scope_params, EMBEDDING_MODEL],
        ).fetchone() is not None
    query_vector = _request_embeddings([question]) if has_scoped_embeddings else None
    if query_vector:
        with _connection() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.filename AS source_title, d.source_type, d.content_hash
                    FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
                    WHERE {scope} AND c.embedding_json IS NOT NULL AND c.embedding_model=? LIMIT 5000""",
                [*scope_params, EMBEDDING_MODEL],
            ).fetchall()
        for row in rows:
            try:
                similarity = _cosine(query_vector[0], json.loads(row["embedding_json"]))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            item = dict(row)
            item["kind"] = "document"
            item["semantic_score"] = similarity
            lexical = evidence_by_id.get(item["id"], {}).get("relevance", 0.0)
            item["relevance"] = max(lexical, max(0.0, similarity))
            evidence_by_id[item["id"]] = item

    evidence = list(evidence_by_id.values())
    if project_id and project_id in db.PROJECTS:
        project = db.PROJECTS[project_id]
        active_revision = revision_id or project.get("revision_id")
        revision = db.get_board_revision(active_revision) if active_revision else None
        snapshot = (revision or {}).get("analysis") or {}
        for kind, label in (("pcb_analysis", "PCB analysis"), ("dfm_result", "DFM findings"),
                            ("bom_result", "BOM and components"), ("recommendation", "Supplier planning"),
                            ("physical_inspection", "Recorded inspection"), ("build_plan", "Build plan")):
            value = snapshot.get(kind) if snapshot else None
            if value is None and active_revision == project.get("revision_id"):
                value = project.get(kind)
            if value:
                rendered = json.dumps(value, ensure_ascii=False, default=str)
                score = sum(1 for token in tokens if token in rendered.lower()) / max(1, len(tokens))
                if score > 0:
                    evidence.append({
                        "id": f"PRJ-{project_id}-{kind}", "kind": "project_record",
                        "source_title": f"{label} · {project.get('filename', project_id)}",
                        "project_id": project_id, "revision_id": active_revision,
                        "page_number": None, "section_title": label, "content": rendered,
                        "relevance": score, "revision_number": (revision or {}).get("revision_number"),
                    })
        if revision and revision.get("analysis"):
            evidence.append({
                "id": f"REV-{revision['id']}", "kind": "revision_record",
                "source_title": f"PCB revision {revision.get('revision_number')} · {revision.get('filename')}",
                "project_id": project_id, "revision_id": revision["id"],
                "content": json.dumps(revision["analysis"], ensure_ascii=False),
                "relevance": 0.15, "page_number": None,
            })
    evidence.sort(key=lambda row: (row.get("relevance", 0), row["kind"] == "project_record"), reverse=True)
    return evidence[:limit]


def answer(question: str, evidence: list[dict]) -> dict:
    threshold = float(os.getenv("KNOWLEDGE_MIN_RELEVANCE", "0.08"))
    if not evidence or max((item.get("relevance", 0) for item in evidence), default=0) < threshold:
        return {"answer": ABSTENTION, "abstained": True, "sources": [], "model_status": "not_used"}
    return {
        "answer": "I found the following evidence. Review the cited source passages below; an AI interpretation is unavailable until the Gemma 4 service is configured.",
        "abstained": False, "sources": evidence, "model_status": "evidence_only",
    }