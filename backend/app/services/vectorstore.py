"""LanceDB vector store with SPECTER2 embeddings."""

import json
from pathlib import Path

import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

from ..config import LANCEDB_DIR

TABLE_NAME = "paper_chunks"

# Use a smaller, faster model for initial setup. SPECTER2 can be swapped in later.
# all-MiniLM-L6-v2 is 80MB vs SPECTER2's 440MB — much faster to download.
DEFAULT_MODEL = "all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None
_db: lancedb.DBConnection | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(DEFAULT_MODEL)
    return _model


def get_db() -> lancedb.DBConnection:
    global _db
    if _db is None:
        LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
        _db = lancedb.connect(str(LANCEDB_DIR))
    return _db


SCHEMA = pa.schema(
    [
        pa.field("vector", pa.list_(pa.float32(), 384)),  # all-MiniLM-L6-v2 = 384-dim
        pa.field("chunk_id", pa.utf8()),
        pa.field("doc_id", pa.utf8()),
        pa.field("text", pa.utf8()),
        pa.field("doc_title", pa.utf8()),
        pa.field("authors", pa.utf8()),
        pa.field("year", pa.int32()),
        pa.field("section", pa.utf8()),
        pa.field("study_label", pa.utf8()),
        pa.field("page_start", pa.int32()),
        pa.field("page_end", pa.int32()),
        pa.field("paragraph_index", pa.int32()),
        pa.field("char_offset_start", pa.int64()),
        pa.field("char_offset_end", pa.int64()),
        pa.field("is_table", pa.bool_()),
        pa.field("is_supplementary", pa.bool_()),
    ]
)


def get_or_create_table():
    db = get_db()
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)


def embed_and_store(chunks_data: list[dict], title: str, authors: str, year: int | None):
    """Embed chunks and store in LanceDB."""
    if not chunks_data:
        return 0

    model = get_model()
    texts = [c["text"] for c in chunks_data]

    # Batch encode
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)

    # Build records
    records = []
    for chunk, embedding in zip(chunks_data, embeddings):
        records.append(
            {
                "vector": embedding.tolist(),
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "text": chunk["text"],
                "doc_title": title or "",
                "authors": authors or "",
                "year": year or 0,
                "section": chunk["section"],
                "study_label": chunk["study_label"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "paragraph_index": chunk["paragraph_index"],
                "char_offset_start": chunk["char_offset_start"],
                "char_offset_end": chunk["char_offset_end"],
                "is_table": chunk["is_table"],
                "is_supplementary": chunk["is_supplementary"],
            }
        )

    table = get_or_create_table()
    table.add(records)
    return len(records)


def search(query: str, limit: int = 20, doc_id: str | None = None) -> list[dict]:
    """Search for similar chunks."""
    model = get_model()
    query_embedding = model.encode([query])[0].tolist()

    table = get_or_create_table()
    results = table.search(query_embedding).limit(limit)

    if doc_id:
        results = results.where(f"doc_id = '{doc_id}'")

    table_result = results.to_arrow()
    return table_result.to_pylist()


def get_table_count() -> int:
    """Get total number of chunks in the vector store."""
    try:
        table = get_or_create_table()
        return table.count_rows()
    except Exception:
        return 0
