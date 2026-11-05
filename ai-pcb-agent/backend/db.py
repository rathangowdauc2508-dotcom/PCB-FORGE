"""SQLite persistence for manufacturing requests and in-memory analysis data."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from contextlib import contextmanager
import uuid

DB_PATH = Path(__file__).parent / "data" / "app.db"
_lock = Lock()

# In-memory stores for rich nested objects (fine for a single-process demo)
PROJECTS: dict[str, dict] = {}
EVENTS: dict[str, list[dict]] = {}


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _connection():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _lock:
        conn = get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pcb_projects (
                id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                pcb_id TEXT,
                manufacturer_id TEXT,
                manufacturer_name TEXT,
                quantity INTEGER,
                total_price REAL,
                estimated_delivery_days INTEGER,
                status TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS payment_attempts (
                order_id TEXT PRIMARY KEY REFERENCES orders(id),
                provider_order_id TEXT UNIQUE NOT NULL,
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                payment_id TEXT,
                created_at TEXT NOT NULL
            );            CREATE TABLE IF NOT EXISTS board_revisions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES pcb_projects(id) ON DELETE CASCADE,
                revision_number INTEGER NOT NULL CHECK (revision_number > 0),
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                byte_size INTEGER NOT NULL CHECK (byte_size > 0),
                created_at TEXT NOT NULL,
                parent_revision_id TEXT REFERENCES board_revisions(id),
                analysis_status TEXT NOT NULL DEFAULT 'not_run',
                analysis_json TEXT,
                tool_version TEXT,
                UNIQUE(project_id, revision_number)
            );
            CREATE INDEX IF NOT EXISTS idx_board_revisions_project
                ON board_revisions(project_id, revision_number);
            CREATE INDEX IF NOT EXISTS idx_board_revisions_hash
                ON board_revisions(project_id, sha256);
            """
        )
        conn.commit()
        rows = conn.execute("SELECT data_json FROM pcb_projects").fetchall()
        for row in rows:
            try:
                project = json.loads(row["data_json"])
                PROJECTS[project["id"]] = project
                EVENTS.setdefault(project["id"], [])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        conn.close()


def save_project(project: dict):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO pcb_projects (id, data_json) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data_json=excluded.data_json",
            (project["id"], json.dumps(project, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()


def delete_project_workspace(project_id: str) -> list[str]:
    """Delete one saved workspace and return its recorded file paths."""
    paths: list[str] = []
    with _lock, _connection() as conn:
        revisions = conn.execute(
            "SELECT id, storage_path FROM board_revisions WHERE project_id=? ORDER BY revision_number DESC",
            (project_id,),
        ).fetchall()
        paths = [row["storage_path"] for row in revisions]
        order_ids = [row["id"] for row in conn.execute(
            "SELECT id FROM orders WHERE pcb_id=?", (project_id,)
        ).fetchall()]
        for order_id in order_ids:
            conn.execute("DELETE FROM payment_attempts WHERE order_id=?", (order_id,))
        conn.execute("DELETE FROM orders WHERE pcb_id=?", (project_id,))
        has_knowledge = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_documents'"
        ).fetchone()
        if has_knowledge:
            paths.extend(row["storage_path"] for row in conn.execute(
                "SELECT storage_path FROM knowledge_documents WHERE project_id=?", (project_id,)
            ).fetchall())
            conn.execute("DELETE FROM knowledge_documents WHERE project_id=?", (project_id,))
        for revision in revisions:
            conn.execute("DELETE FROM board_revisions WHERE id=?", (revision["id"],))
        conn.execute("DELETE FROM pcb_projects WHERE id=?", (project_id,))
    PROJECTS.pop(project_id, None)
    EVENTS.pop(project_id, None)
    return paths


def delete_project(project_id: str) -> None:
    """Remove a project; used when its initial upload fails validation."""
    delete_project_workspace(project_id)

def save_order(order: dict):
    with _lock:
        conn = get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO orders
               (id, pcb_id, manufacturer_id, manufacturer_name, quantity, total_price,
                estimated_delivery_days, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                order["id"], order["pcb_id"], order["manufacturer_id"], order["manufacturer_name"],
                order["quantity"], order["total_price"], order["estimated_delivery_days"],
                order["status"], order["created_at"],
            ),
        )
        conn.commit()
        conn.close()


def save_payment_attempt(payment: dict) -> None:
    with _lock:
        conn = get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO payment_attempts
               (order_id, provider_order_id, amount_minor, currency, status, payment_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (payment["order_id"], payment["provider_order_id"], payment["amount_minor"],
             payment["currency"], payment["status"], payment.get("payment_id"), payment["created_at"]),
        )
        conn.commit()
        conn.close()


def get_payment_attempt(provider_order_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_attempts WHERE provider_order_id=?",
            (provider_order_id,),
        ).fetchone()
    return dict(row) if row else None


def update_payment_attempt(provider_order_id: str, status: str, payment_id: str | None = None) -> None:
    with _lock:
        conn = get_conn()
        conn.execute(
            "UPDATE payment_attempts SET status=?, payment_id=COALESCE(?, payment_id) WHERE provider_order_id=?",
            (status, payment_id, provider_order_id),
        )
        conn.commit()
        conn.close()


def update_order_status(order_id: str, status: str) -> None:
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        conn.commit()
        conn.close()

def get_order(order_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_event(project_id: str, event: dict):
    EVENTS.setdefault(project_id, []).append(event)


def get_events(project_id: str) -> list[dict]:
    return EVENTS.get(project_id, [])


def create_board_revision(
    project_id: str,
    filename: str,
    storage_path: str,
    sha256: str,
    byte_size: int,
    created_at: str,
    parent_revision_id: str | None = None,
) -> dict:
    """Persist immutable source metadata and return the newly assigned revision."""
    revision_id = f"REV-{uuid.uuid4().hex[:12].upper()}"
    with _lock, _connection() as conn:
        if parent_revision_id:
            parent = conn.execute(
                "SELECT id FROM board_revisions WHERE id=? AND project_id=?",
                (parent_revision_id, project_id),
            ).fetchone()
            if not parent:
                raise ValueError("Parent revision does not belong to this project.")
        number = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM board_revisions WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO board_revisions
               (id, project_id, revision_number, filename, storage_path, sha256, byte_size,
                created_at, parent_revision_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (revision_id, project_id, number, filename, storage_path, sha256, byte_size,
             created_at, parent_revision_id),
        )
    return get_board_revision(revision_id)


def get_board_revision(revision_id: str) -> dict | None:
    with _connection() as conn:
        row = conn.execute("SELECT * FROM board_revisions WHERE id=?", (revision_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("analysis_json"):
        try:
            result["analysis"] = json.loads(result.pop("analysis_json"))
        except json.JSONDecodeError:
            result["analysis"] = None
    else:
        result.pop("analysis_json", None)
        result["analysis"] = None
    return result


def list_board_revisions(project_id: str) -> list[dict]:
    with _connection() as conn:
        ids = conn.execute(
            "SELECT id FROM board_revisions WHERE project_id=? ORDER BY revision_number DESC",
            (project_id,),
        ).fetchall()
    return [get_board_revision(row["id"]) for row in ids]


def set_revision_status(revision_id: str, status: str) -> None:
    if status not in {"not_run", "running", "completed", "failed"}:
        raise ValueError("Unsupported revision analysis status.")
    with _lock, _connection() as conn:
        conn.execute("UPDATE board_revisions SET analysis_status=? WHERE id=?", (status, revision_id))

def save_revision_analysis(revision_id: str, analysis: dict, tool_version: str, status: str = "completed") -> None:
    with _lock, _connection() as conn:
        conn.execute(
            "UPDATE board_revisions SET analysis_json=?, tool_version=?, analysis_status=? WHERE id=?",
            (json.dumps(analysis, ensure_ascii=False), tool_version, status, revision_id),
        )


def add_history(project_id: str, action: str, detail: str) -> None:
    """Append a small audit entry to the project's durable JSON record."""
    project = PROJECTS.get(project_id)
    if not project:
        return
    project.setdefault("history", []).append({
        "id": uuid.uuid4().hex[:12],
        "action": action,
        "detail": detail,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    save_project(project)

# permission-write-check


