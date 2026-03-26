"""Search router: template upload, AI extraction with progress streaming."""

import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_connection
from ..services.vectorstore import search as vector_search
from ..services.pdf_parser import extract_doc_id
from ..services import ai_service

router = APIRouter(prefix="/search", tags=["search"])


class TemplateUpload(BaseModel):
    name: str
    type: str  # 'input' | 'output'
    format: str
    content: str


class SearchRequest(BaseModel):
    input_template_id: str | None = None
    output_template_id: str | None = None
    prompt_text: str | None = None
    doc_ids: list[str] | None = None


# --- Template endpoints ---


@router.post("/templates")
async def upload_template(req: TemplateUpload):
    template_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO templates (id, name, type, format, content)
           VALUES (?, ?, ?, ?, ?)""",
        (template_id, req.name, req.type, req.format, req.content),
    )
    conn.commit()
    conn.close()
    return {"id": template_id, "name": req.name}


@router.get("/templates")
async def list_templates(type: str | None = None):
    conn = get_connection()
    if type:
        rows = conn.execute(
            "SELECT id, name, type, format, created_at FROM templates WHERE type = ? ORDER BY created_at DESC",
            (type,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, type, format, created_at FROM templates ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    conn = get_connection()
    # Clear foreign key references first
    conn.execute(
        "UPDATE search_sessions SET input_template_id = NULL WHERE input_template_id = ?",
        (template_id,),
    )
    conn.execute(
        "UPDATE search_sessions SET output_template_id = NULL WHERE output_template_id = ?",
        (template_id,),
    )
    result = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": template_id}


# --- AI status ---


@router.get("/ai-status")
async def ai_status():
    """Check Claude CLI availability with detailed status."""
    return ai_service.check_status()


# --- Search execution with SSE progress ---


@router.post("/execute")
async def execute_search(req: SearchRequest):
    """Execute search with Server-Sent Events for progress."""
    if not req.input_template_id and not req.prompt_text:
        raise HTTPException(
            status_code=400,
            detail="At least one of Import Requirements template or prompt text is required.",
        )

    # Pre-check AI status
    status = ai_service.check_status()
    if not status["available"]:
        raise HTTPException(status_code=503, detail=status["error"])

    conn = get_connection()

    # Load templates
    template_text = ""
    if req.input_template_id:
        row = conn.execute(
            "SELECT content FROM templates WHERE id = ?", (req.input_template_id,)
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Import Requirements template not found.")
        template_text = row["content"]

    output_template_text = ""
    if req.output_template_id:
        row = conn.execute(
            "SELECT content FROM templates WHERE id = ?", (req.output_template_id,)
        ).fetchone()
        if row:
            output_template_text = row["content"]

    # Get papers
    if req.doc_ids:
        placeholders = ",".join("?" * len(req.doc_ids))
        papers = conn.execute(
            f"SELECT id, filename, filepath, title FROM papers WHERE id IN ({placeholders}) AND import_status = 'vectorized'",
            req.doc_ids,
        ).fetchall()
    else:
        papers = conn.execute(
            "SELECT id, filename, filepath, title FROM papers WHERE import_status = 'vectorized'"
        ).fetchall()

    if not papers:
        conn.close()
        raise HTTPException(status_code=404, detail="No vectorized papers found. Complete Phase 3 (Vectorize) first.")

    conn.close()

    # Stream progress via SSE
    def generate():
        nonlocal conn
        conn = get_connection()

        session_id = str(uuid.uuid4())[:8]
        conn.execute(
            """INSERT INTO search_sessions (id, input_template_id, output_template_id, prompt_text, status)
               VALUES (?, ?, ?, ?, 'running')""",
            (session_id, req.input_template_id, req.output_template_id, req.prompt_text),
        )
        conn.commit()

        combined_template = template_text
        if output_template_text:
            combined_template += f"\n\n--- Export Results Format ---\n{output_template_text}"

        total = len(papers)
        completed = 0
        error_count = 0

        # Send initial status
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'total': total})}\n\n"

        for paper in papers:
            paper_id = paper["id"]
            # Use the numeric doc_id from filename (matches LanceDB)
            doc_id = extract_doc_id(paper["filename"]) if paper["filename"] else paper_id
            doc_title = paper["title"] or paper["filepath"] or doc_id

            yield f"data: {json.dumps({'type': 'progress', 'current': completed + 1, 'total': total, 'paper': doc_title[:80]})}\n\n"

            try:
                search_query = req.prompt_text or template_text[:500]
                chunks = vector_search(search_query, limit=30, doc_id=doc_id)

                if not chunks:
                    yield f"data: {json.dumps({'type': 'skip', 'paper': doc_title[:80], 'reason': 'No matching chunks found'})}\n\n"
                    completed += 1
                    continue

                extraction = ai_service.extract_fields_from_chunks(
                    chunks=chunks,
                    template_text=combined_template,
                    prompt_text=req.prompt_text or "",
                    doc_title=doc_title,
                )

                result_id = str(uuid.uuid4())[:8]
                conn.execute(
                    """INSERT INTO search_results (id, session_id, doc_id, result_data, citations)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        result_id,
                        session_id,
                        paper_id,
                        json.dumps(extraction.get("fields", {})),
                        json.dumps(extraction.get("citations", {})),
                    ),
                )
                conn.commit()

                yield f"data: {json.dumps({'type': 'result', 'paper': doc_title[:80], 'fields': extraction.get('fields', {})})}\n\n"

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                yield f"data: {json.dumps({'type': 'error', 'paper': doc_title[:80], 'error': error_msg[:300]})}\n\n"

            completed += 1

        conn.execute(
            "UPDATE search_sessions SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'completed': completed, 'errors': error_count})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
