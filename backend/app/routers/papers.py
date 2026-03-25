import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_connection
from ..services.pdf_parser import parse_pdf
from ..services.vectorstore import embed_and_store, get_table_count

router = APIRouter(prefix="/papers", tags=["papers"])


class ImportRequest(BaseModel):
    paths: list[str]


class PaperResponse(BaseModel):
    id: str
    filename: str
    filepath: str | None
    title: str | None
    authors: str | None
    year: int | None
    import_status: str
    page_count: int | None
    chunk_count: int | None
    imported_at: str | None


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


def _collect_pdfs(paths: list[str]) -> list[Path]:
    """Collect all PDF files from a list of file/folder paths."""
    pdfs = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            pdfs.extend(sorted(path.rglob("*.pdf")))
            pdfs.extend(sorted(path.rglob("*.PDF")))
        elif path.is_file() and path.suffix.lower() == ".pdf":
            pdfs.append(path)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for pdf in pdfs:
        resolved = pdf.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


@router.post("/import", response_model=ImportResult)
async def import_papers(req: ImportRequest):
    """Import PDF papers from file/folder paths."""
    pdfs = _collect_pdfs(req.paths)
    conn = get_connection()
    imported = 0
    skipped = 0
    errors = []

    for pdf_path in pdfs:
        # Check if already imported (by filepath)
        existing = conn.execute(
            "SELECT id FROM papers WHERE filepath = ?", (str(pdf_path),)
        ).fetchone()
        if existing:
            skipped += 1
            continue

        try:
            paper_id = str(uuid.uuid4())[:8]
            conn.execute(
                """INSERT INTO papers (id, filename, filepath, import_status)
                   VALUES (?, ?, ?, 'pending')""",
                (paper_id, pdf_path.name, str(pdf_path)),
            )
            imported += 1
        except Exception as e:
            errors.append(f"{pdf_path.name}: {e}")

    conn.commit()
    conn.close()
    return ImportResult(imported=imported, skipped=skipped, errors=errors)


@router.get("/", response_model=list[PaperResponse])
async def list_papers(status: str | None = None, limit: int = 100, offset: int = 0):
    """List imported papers with optional status filter."""
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM papers WHERE import_status = ? ORDER BY imported_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM papers ORDER BY imported_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/count")
async def count_papers():
    """Get paper counts by status."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT import_status, COUNT(*) as count FROM papers GROUP BY import_status"
    ).fetchall()
    conn.close()
    return {r["import_status"]: r["count"] for r in rows}


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str):
    """Remove a paper from the database."""
    conn = get_connection()
    result = conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"deleted": paper_id}


class ParseResponse(BaseModel):
    processed: int
    skipped: int
    errors: list[str]


@router.post("/parse", response_model=ParseResponse)
async def parse_papers():
    """Parse all pending PDFs into text chunks."""
    conn = get_connection()
    pending = conn.execute(
        "SELECT id, filepath FROM papers WHERE import_status = 'pending'"
    ).fetchall()

    processed = 0
    skipped = 0
    errors = []

    for row in pending:
        paper_id = row["id"]
        filepath = row["filepath"]

        if not filepath or not Path(filepath).exists():
            conn.execute(
                "UPDATE papers SET import_status = 'error' WHERE id = ?",
                (paper_id,),
            )
            errors.append(f"{filepath}: file not found")
            continue

        try:
            result = parse_pdf(Path(filepath))

            if result.is_mostly_scanned:
                conn.execute(
                    "UPDATE papers SET import_status = 'skipped_ocr', page_count = ? WHERE id = ?",
                    (result.page_count, paper_id),
                )
                skipped += 1
                continue

            # Store chunks as JSON in a new chunks field (or we'll use LanceDB later)
            import json

            chunks_data = json.dumps(
                [
                    {
                        "chunk_id": c.chunk_id,
                        "doc_id": c.doc_id,
                        "text": c.text,
                        "section": c.section,
                        "study_label": c.study_label,
                        "page_start": c.page_start,
                        "page_end": c.page_end,
                        "paragraph_index": c.paragraph_index,
                        "char_offset_start": c.char_offset_start,
                        "char_offset_end": c.char_offset_end,
                        "is_table": c.is_table,
                        "is_supplementary": c.is_supplementary,
                    }
                    for c in result.chunks
                ]
            )

            conn.execute(
                """UPDATE papers SET
                    import_status = 'parsed',
                    title = ?,
                    authors = ?,
                    year = ?,
                    page_count = ?,
                    chunk_count = ?
                WHERE id = ?""",
                (
                    result.title,
                    result.authors,
                    result.year,
                    result.page_count,
                    len(result.chunks),
                    paper_id,
                ),
            )
            processed += 1
        except Exception as e:
            conn.execute(
                "UPDATE papers SET import_status = 'error' WHERE id = ?",
                (paper_id,),
            )
            errors.append(f"{filepath}: {e}")

    conn.commit()
    conn.close()
    return ParseResponse(processed=processed, skipped=skipped, errors=errors)


class VectorizeResponse(BaseModel):
    vectorized: int
    errors: list[str]


@router.post("/vectorize", response_model=VectorizeResponse)
async def vectorize_papers():
    """Vectorize parsed papers and store in LanceDB."""
    import json as json_mod

    conn = get_connection()
    parsed = conn.execute(
        "SELECT id, filepath, title, authors, year FROM papers WHERE import_status = 'parsed'"
    ).fetchall()

    vectorized = 0
    errors = []

    for row in parsed:
        paper_id = row["id"]
        filepath = row["filepath"]

        try:
            # Re-parse to get chunks (lightweight since we already validated)
            result = parse_pdf(Path(filepath))
            chunks_data = [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "text": c.text,
                    "section": c.section,
                    "study_label": c.study_label,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "paragraph_index": c.paragraph_index,
                    "char_offset_start": c.char_offset_start,
                    "char_offset_end": c.char_offset_end,
                    "is_table": c.is_table,
                    "is_supplementary": c.is_supplementary,
                }
                for c in result.chunks
            ]

            count = embed_and_store(
                chunks_data,
                title=row["title"] or "",
                authors=row["authors"] or "",
                year=row["year"],
            )

            conn.execute(
                "UPDATE papers SET import_status = 'vectorized', chunk_count = ? WHERE id = ?",
                (count, paper_id),
            )
            vectorized += 1
        except Exception as e:
            errors.append(f"{filepath}: {e}")

    conn.commit()
    conn.close()
    return VectorizeResponse(vectorized=vectorized, errors=errors)


@router.get("/vector-count")
async def vector_count():
    """Get total chunks in vector store."""
    return {"count": get_table_count()}
