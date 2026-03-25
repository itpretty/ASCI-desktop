import sqlite3
from pathlib import Path
from .config import SQLITE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT,
    title TEXT,
    authors TEXT,
    year INTEGER,
    import_status TEXT NOT NULL DEFAULT 'pending',
    page_count INTEGER,
    chunk_count INTEGER,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    format TEXT NOT NULL,
    content TEXT NOT NULL,
    parsed_schema TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_sessions (
    id TEXT PRIMARY KEY,
    input_template_id TEXT REFERENCES templates(id),
    output_template_id TEXT REFERENCES templates(id),
    prompt_text TEXT,
    field_mappings TEXT,
    status TEXT NOT NULL DEFAULT 'configured',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE TABLE IF NOT EXISTS search_results (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES search_sessions(id),
    doc_id TEXT NOT NULL,
    study_id TEXT,
    result_data TEXT NOT NULL,
    citations TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS result_edits (
    id TEXT PRIMARY KEY,
    result_id TEXT REFERENCES search_results(id),
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    edited_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.close()
