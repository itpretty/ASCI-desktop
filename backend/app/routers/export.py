"""Export router: export results to xlsx, pdf, md with file management."""

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..config import DATA_DIR
from ..database import get_connection
from ..services.exporter import export_xlsx, export_md, export_pdf

router = APIRouter(prefix="/export", tags=["export"])

EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _generate_title(session_id: str) -> str:
    """Generate a brief title from the session's template/prompt."""
    conn = get_connection()
    row = conn.execute(
        """SELECT s.prompt_text, t.name as template_name
           FROM search_sessions s
           LEFT JOIN templates t ON s.input_template_id = t.id
           WHERE s.id = ?""",
        (session_id,),
    ).fetchone()
    conn.close()

    if not row:
        return "export"

    # Use template name or first few words of prompt
    if row["template_name"]:
        name = Path(row["template_name"]).stem
        # Clean to filesystem-safe chars
        name = re.sub(r"[^\w\s-]", "", name).strip()[:30]
        return name or "export"
    elif row["prompt_text"]:
        words = row["prompt_text"].split()[:4]
        name = "-".join(words)
        name = re.sub(r"[^\w\s-]", "", name).strip()[:30]
        return name or "export"
    return "export"


class ExportRequest(BaseModel):
    session_id: str | None = None
    result_ids: list[str] | None = None
    format: str  # 'xlsx' | 'pdf' | 'md'


@router.post("/")
async def export_results(req: ExportRequest):
    """Export search results, save to disk, and return file info."""
    conn = get_connection()

    if req.result_ids:
        placeholders = ",".join("?" * len(req.result_ids))
        results = conn.execute(
            f"""SELECT sr.*, p.title as doc_title, p.filename
                FROM search_results sr
                LEFT JOIN papers p ON sr.doc_id = p.id
                WHERE sr.id IN ({placeholders})""",
            req.result_ids,
        ).fetchall()
    elif req.session_id:
        results = conn.execute(
            """SELECT sr.*, p.title as doc_title, p.filename
               FROM search_results sr
               LEFT JOIN papers p ON sr.doc_id = p.id
               WHERE sr.session_id = ?""",
            (req.session_id,),
        ).fetchall()
    else:
        results = conn.execute(
            """SELECT sr.*, p.title as doc_title, p.filename
               FROM search_results sr
               LEFT JOIN papers p ON sr.doc_id = p.id
               ORDER BY sr.created_at DESC LIMIT 100"""
        ).fetchall()

    conn.close()

    if not results:
        raise HTTPException(status_code=404, detail="No results to export")

    result_dicts = [dict(r) for r in results]

    # Generate filename
    session_id = req.session_id or "all"
    title = _generate_title(session_id) if req.session_id else "export"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    basename = f"{timestamp}-{session_id}-{title}"

    ext = req.format
    filename = f"{basename}.{ext}"
    filepath = EXPORTS_DIR / filename

    if req.format == "xlsx":
        content = export_xlsx(result_dicts)
        filepath.write_bytes(content)
    elif req.format == "md":
        content = export_md(result_dicts)
        filepath.write_text(content, encoding="utf-8")
    elif req.format == "pdf":
        content = export_pdf(result_dicts)
        filepath.write_bytes(content)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    return {
        "filename": filename,
        "path": str(filepath),
        "format": req.format,
        "session_id": session_id,
    }


@router.get("/files")
async def list_exports(session_id: str | None = None):
    """List exported files, optionally filtered by session_id."""
    files = []
    for f in sorted(EXPORTS_DIR.iterdir(), reverse=True):
        if not f.is_file():
            continue
        info = {
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "format": f.suffix.lstrip("."),
        }
        # Extract session_id from filename: YYYYMMDD-HHMM-{session_id}-{title}.ext
        parts = f.stem.split("-", 3)
        if len(parts) >= 3:
            info["session_id"] = parts[2]
        files.append(info)

    if session_id:
        files = [f for f in files if f.get("session_id") == session_id]

    return files


@router.get("/download/{filename}")
async def download_export(filename: str):
    """Download an exported file."""
    filepath = EXPORTS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_types = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
        ".md": "text/markdown",
    }
    media_type = media_types.get(filepath.suffix, "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type=media_type,
    )


@router.delete("/files/{filename}")
async def delete_export(filename: str):
    """Delete an exported file."""
    filepath = EXPORTS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    filepath.unlink()
    return {"deleted": filename}
