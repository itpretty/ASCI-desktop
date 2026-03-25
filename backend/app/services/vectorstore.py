"""LanceDB vector store with ONNX Runtime embeddings."""

from pathlib import Path

import lancedb
import numpy as np
import onnxruntime as ort
import pyarrow as pa
from tokenizers import Tokenizer

from ..config import LANCEDB_DIR

TABLE_NAME = "paper_chunks"
EMBEDDING_DIM = 384
MAX_SEQ_LENGTH = 256

# Model path relative to backend directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = _BACKEND_DIR / "models" / "all-MiniLM-L6-v2"

_session: ort.InferenceSession | None = None
_tokenizer: Tokenizer | None = None
_db: lancedb.DBConnection | None = None


def get_tokenizer() -> Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        tok_path = MODEL_DIR / "tokenizer.json"
        if not tok_path.exists():
            raise FileNotFoundError(f"Tokenizer not found at {tok_path}")
        _tokenizer = Tokenizer.from_file(str(tok_path))
        _tokenizer.enable_padding(length=MAX_SEQ_LENGTH)
        _tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)
    return _tokenizer


def get_session() -> ort.InferenceSession:
    global _session
    if _session is None:
        model_path = MODEL_DIR / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found at {model_path}")
        _session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
    return _session


def _encode_single(text: str) -> np.ndarray:
    """Encode a single text into a normalized embedding."""
    tokenizer = get_tokenizer()
    session = get_session()

    encoded = tokenizer.encode(text)
    input_ids = np.array([encoded.ids], dtype=np.int64)
    attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

    outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
    token_embeddings = outputs[0]  # (1, seq_len, 384)

    # Mean pooling
    expanded_mask = attention_mask[:, :, np.newaxis].astype(np.float32)
    pooled = np.sum(token_embeddings * expanded_mask, axis=1) / np.maximum(
        expanded_mask.sum(axis=1), 1e-9
    )

    # L2 normalize
    norm = np.linalg.norm(pooled)
    return pooled[0] / max(norm, 1e-9)


def encode(texts: list[str]) -> np.ndarray:
    """Encode texts into normalized embeddings using ONNX Runtime."""
    embeddings = [_encode_single(t) for t in texts]
    return np.array(embeddings)


def get_db() -> lancedb.DBConnection:
    global _db
    if _db is None:
        LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
        _db = lancedb.connect(str(LANCEDB_DIR))
    return _db


SCHEMA = pa.schema(
    [
        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
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

    texts = [c["text"] for c in chunks_data]

    # Batch encode (process in chunks of 32 to limit memory)
    all_embeddings = []
    for i in range(0, len(texts), 32):
        batch = texts[i : i + 32]
        embeddings = encode(batch)
        all_embeddings.append(embeddings)
    all_embeddings = np.vstack(all_embeddings)

    # Build records
    records = []
    for chunk, embedding in zip(chunks_data, all_embeddings):
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
    query_embedding = encode([query])[0].tolist()

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
