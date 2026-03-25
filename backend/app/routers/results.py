"""Results router: list sessions, results, edit, re-run."""

import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_connection

router = APIRouter(prefix="/results", tags=["results"])


class SessionResponse(BaseModel):
    id: str
    input_template_id: str | None
    output_template_id: str | None
    prompt_text: str | None
    status: str
    created_at: str | None
    completed_at: str | None
    result_count: int


class ResultResponse(BaseModel):
    id: str
    session_id: str
    doc_id: str
    study_id: str | None
    result_data: str  # JSON string
    citations: str  # JSON string
    created_at: str | None


class EditRequest(BaseModel):
    field_name: str
    new_value: str


# --- Sessions ---


@router.get("/sessions")
async def list_sessions(limit: int = 50, offset: int = 0):
    """List search sessions with result counts."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*,
           (SELECT COUNT(*) FROM search_results WHERE session_id = s.id) as result_count
           FROM search_sessions s
           ORDER BY s.created_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a single session with its results."""
    conn = get_connection()
    session = conn.execute(
        "SELECT * FROM search_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    results = conn.execute(
        """SELECT sr.*, p.title as doc_title, p.filename
           FROM search_results sr
           LEFT JOIN papers p ON sr.doc_id = p.id
           ORDER BY sr.created_at""",
    ).fetchall()
    conn.close()

    return {
        "session": dict(session),
        "results": [dict(r) for r in results],
    }


# --- Results ---


@router.get("/")
async def list_results(session_id: str | None = None, limit: int = 50, offset: int = 0):
    """List search results with optional session filter."""
    conn = get_connection()
    if session_id:
        rows = conn.execute(
            """SELECT sr.*, p.title as doc_title, p.filename
               FROM search_results sr
               LEFT JOIN papers p ON sr.doc_id = p.id
               WHERE sr.session_id = ?
               ORDER BY sr.created_at DESC LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT sr.*, p.title as doc_title, p.filename
               FROM search_results sr
               LEFT JOIN papers p ON sr.doc_id = p.id
               ORDER BY sr.created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.put("/{result_id}")
async def edit_result(result_id: str, req: EditRequest):
    """Edit a field in a search result (with history tracking)."""
    conn = get_connection()
    result = conn.execute(
        "SELECT result_data FROM search_results WHERE id = ?", (result_id,)
    ).fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Result not found")

    # Parse current data
    data = json.loads(result["result_data"])
    old_value = data.get(req.field_name, "")

    # Update field
    data[req.field_name] = req.new_value
    conn.execute(
        "UPDATE search_results SET result_data = ? WHERE id = ?",
        (json.dumps(data), result_id),
    )

    # Track edit
    edit_id = str(uuid.uuid4())[:8]
    conn.execute(
        """INSERT INTO result_edits (id, result_id, field_name, old_value, new_value)
           VALUES (?, ?, ?, ?, ?)""",
        (edit_id, result_id, req.field_name, str(old_value), req.new_value),
    )

    conn.commit()
    conn.close()
    return {"updated": result_id, "field": req.field_name}


@router.delete("/{result_id}")
async def delete_result(result_id: str):
    conn = get_connection()
    result = conn.execute("DELETE FROM search_results WHERE id = ?", (result_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"deleted": result_id}
