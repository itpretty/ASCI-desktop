"""Search router: template upload, field matching, AI extraction."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_connection
from ..services.vectorstore import search as vector_search
from ..services import ai_service

router = APIRouter(prefix="/search", tags=["search"])


class TemplateUpload(BaseModel):
    name: str
    type: str  # 'input' | 'output'
    format: str  # 'markdown' | 'csv' | 'xlsx' etc.
    content: str


class SearchRequest(BaseModel):
    input_template_id: str | None = None
    output_template_id: str | None = None
    prompt_text: str | None = None
    doc_ids: list[str] | None = None  # specific papers, or None for all


class SearchResultItem(BaseModel):
    doc_id: str
    doc_title: str
    fields: dict
    citations: dict


# --- Template endpoints ---


@router.post("/templates")
async def upload_template(req: TemplateUpload):
    """Upload an input or output template."""
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
    """List uploaded templates."""
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
    result = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": template_id}


# --- AI status ---


@router.get("/ai-status")
async def ai_status():
    """Check if Claude CLI is available."""
    return {"available": ai_service.is_available()}


# --- Search execution ---


@router.post("/execute")
async def execute_search(req: SearchRequest):
    """Execute a search: vector retrieval + AI extraction."""
    if not req.input_template_id and not req.prompt_text:
        raise HTTPException(
            status_code=400,
            detail="At least one of input_template_id or prompt_text is required",
        )

    conn = get_connection()

    # Load input template if provided
    template_text = ""
    if req.input_template_id:
        row = conn.execute(
            "SELECT content FROM templates WHERE id = ?", (req.input_template_id,)
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Input template not found")
        template_text = row["content"]

    # Load output template if provided
    output_template_text = ""
    if req.output_template_id:
        row = conn.execute(
            "SELECT content FROM templates WHERE id = ?", (req.output_template_id,)
        ).fetchone()
        if row:
            output_template_text = row["content"]

    # Get papers to process
    if req.doc_ids:
        placeholders = ",".join("?" * len(req.doc_ids))
        papers = conn.execute(
            f"SELECT id, filepath, title FROM papers WHERE id IN ({placeholders}) AND import_status = 'vectorized'",
            req.doc_ids,
        ).fetchall()
    else:
        papers = conn.execute(
            "SELECT id, filepath, title FROM papers WHERE import_status = 'vectorized'"
        ).fetchall()

    # Create search session
    session_id = str(uuid.uuid4())[:8]
    conn.execute(
        """INSERT INTO search_sessions (id, input_template_id, output_template_id, prompt_text, status)
           VALUES (?, ?, ?, ?, 'running')""",
        (session_id, req.input_template_id, req.output_template_id, req.prompt_text),
    )
    conn.commit()

    # Build combined prompt from template + user prompt
    combined_template = template_text
    if output_template_text:
        combined_template += f"\n\n--- Output Format ---\n{output_template_text}"

    results = []
    errors = []

    for paper in papers:
        doc_id = paper["id"]
        doc_title = paper["title"] or paper["filepath"] or doc_id

        try:
            # Vector search for this paper's relevant chunks
            search_query = req.prompt_text or template_text[:500]
            chunks = vector_search(search_query, limit=30, doc_id=doc_id)

            if not chunks:
                continue

            # AI extraction
            extraction = ai_service.extract_fields_from_chunks(
                chunks=chunks,
                template_text=combined_template,
                prompt_text=req.prompt_text or "",
                doc_title=doc_title,
            )

            # Save result
            result_id = str(uuid.uuid4())[:8]
            conn.execute(
                """INSERT INTO search_results (id, session_id, doc_id, result_data, citations)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    result_id,
                    session_id,
                    doc_id,
                    json.dumps(extraction.get("fields", {})),
                    json.dumps(extraction.get("citations", {})),
                ),
            )

            results.append(
                SearchResultItem(
                    doc_id=doc_id,
                    doc_title=doc_title,
                    fields=extraction.get("fields", {}),
                    citations=extraction.get("citations", {}),
                )
            )

        except Exception as e:
            errors.append(f"{doc_title}: {e}")

    # Update session status
    conn.execute(
        "UPDATE search_sessions SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "results": [r.model_dump() for r in results],
        "errors": errors,
    }
