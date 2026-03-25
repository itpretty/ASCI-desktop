"""Export router: export results to xlsx, pdf, md."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..database import get_connection
from ..services.exporter import export_xlsx, export_md, export_pdf

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    session_id: str | None = None
    result_ids: list[str] | None = None
    format: str  # 'xlsx' | 'pdf' | 'md'


@router.post("/")
async def export_results(req: ExportRequest):
    """Export search results in the specified format."""
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

    if req.format == "xlsx":
        content = export_xlsx(result_dicts)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=asci_export.xlsx"},
        )
    elif req.format == "md":
        content = export_md(result_dicts)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=asci_export.md"},
        )
    elif req.format == "pdf":
        content = export_pdf(result_dicts)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=asci_export.pdf"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")
