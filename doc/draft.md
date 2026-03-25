# Design a desktop app "ASCI-Desktop"

This is an academic tool to help researchers read and analyse papers, save the analysis results into a vector DB and extract data as per custom templates of input and output.

## Stack

- Desktop framework: Tauri v2 (https://v2.tauri.app/)
- Backend: Python 3.11+ (FastAPI, packaged as Tauri sidecar via PyInstaller)
- Frontend: React + Tailwind CSS
- AI model: Claude Code CLI (`claude -p`)
- Embedding: ONNX Runtime + all-MiniLM-L6-v2 (local, 384-dim, ~88 MB)
- Vector DB: LanceDB (embedded, Python SDK)
- Relational DB: SQLite (via `tauri-plugin-sql`)
- PDF parsing: PyMuPDF (primary) + pdfplumber (tables)
- Export: openpyxl (.xlsx), weasyprint (.pdf), string formatting (.md)

### Python dependencies

```
lancedb
onnxruntime
tokenizers
PyMuPDF
pdfplumber
openpyxl
weasyprint
fastapi
uvicorn
```

## Tauri + Python Integration

The Python backend runs as a **Tauri sidecar** process:

- **Development**: Run a local FastAPI server on localhost; Tauri frontend communicates via HTTP
- **Production**: Freeze the Python backend with PyInstaller into a standalone binary, bundled alongside the Tauri app via `tauri-plugin-shell` sidecar support
- **Communication**: Local HTTP (REST) between Tauri frontend and Python sidecar
- **Lifecycle**: Tauri starts the sidecar on app launch and stops it on app close

Considerations:
- Sidecar adds 50-150MB to app size (frozen Python runtime)
- Startup latency of 2-5s requires a loading indicator in the UI
- macOS: sidecar binary needs separate code signing and notarization
- Cross-platform CI/CD needed for macOS, Windows, Linux builds

## AI Service

- Create a server using Python
- Use session running on current machine by `claude -p`
- Use Claude Code Team account on top priority
- Use account with API Key secondly
- In future, AI service will cover other AI models by CLI and API key
- This server will be wrapped and running in Tauri

### Error handling

- Graceful degradation when AI service is unavailable: allow PDF import, parsing, and local vector search without AI
- Queue AI tasks for when connectivity returns

## Embedding Model

- **Default**: all-MiniLM-L6-v2 via ONNX Runtime (~88 MB total)
  - Runs locally via ONNX Runtime (no PyTorch dependency)
  - 384-dim embeddings, good retrieval quality
  - Offline-capable
  - Can be swapped to SPECTER2 or other models by exporting to ONNX
- **Optional upgrade**: Voyage AI `voyage-3-large` (API-based, 1024-dim) when online
- The embedding model handles recall (retrieving candidate chunks); Claude handles precision (exact field extraction from retrieved chunks)

## UI

- Extremely simple and clean style
- Look more like a scientific tool/platform not an AI one
- Do not use too many vivid colors
- Loading indicator during sidecar startup (2-5s)
- Progress bars for batch operations (PDF import, embedding, AI extraction)

## Data Storage

### LanceDB (vectors only)

LanceDB runs embedded (no server, Lance files on disk) inside the Python sidecar. Schema:

```
Table: paper_chunks
  - vector: Float32[768]       # SPECTER2 embedding
  - chunk_id: String           # e.g. "151_methods_p3_c2"
  - doc_id: String             # filename-derived, e.g. "151"
  - text: String               # chunk text content
  - doc_title: String
  - authors: String
  - year: Int32
  - section: String            # detected section name
  - study_label: String        # e.g. "Study 2" for multi-study papers
  - page_start: Int32
  - page_end: Int32
  - paragraph_index: Int32
  - char_offset_start: Int64
  - char_offset_end: Int64
  - is_table: Boolean
  - is_supplementary: Boolean
```

### SQLite (relational data)

SQLite handles CRUD, pagination, edit history, and template storage:

```sql
CREATE TABLE papers (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT,
    authors TEXT,
    year INTEGER,
    import_status TEXT NOT NULL,  -- 'pending'|'parsed'|'vectorized'|'skipped_ocr'|'error'
    page_count INTEGER,
    chunk_count INTEGER,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,           -- 'input'|'output'
    format TEXT NOT NULL,         -- 'markdown'|'csv'|'xlsx' etc.
    content TEXT NOT NULL,
    parsed_schema TEXT,           -- JSON: extracted field definitions
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE search_sessions (
    id TEXT PRIMARY KEY,
    input_template_id TEXT REFERENCES templates(id),
    output_template_id TEXT REFERENCES templates(id),
    prompt_text TEXT,
    field_mappings TEXT,          -- JSON: input-output field mapping + ignored mismatches
    status TEXT NOT NULL,         -- 'configured'|'running'|'completed'|'failed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE TABLE search_results (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES search_sessions(id),
    doc_id TEXT NOT NULL,
    study_id TEXT,
    result_data TEXT NOT NULL,    -- JSON: all extracted field values
    citations TEXT NOT NULL,      -- JSON: per-field provenance
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE result_edits (
    id TEXT PRIMARY KEY,
    result_id TEXT REFERENCES search_results(id),
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    edited_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Storage location

All data stored in OS app data directory:
- macOS: `~/Library/Application Support/ASCI-Desktop/`
- Windows: `%APPDATA%/ASCI-Desktop/`
- Linux: `~/.local/share/ASCI-Desktop/`

Backup: copy the entire directory (files are portable).

## Work Flow

1. Import local PDF papers
2. Parse PDFs into texts and chunks (with metadata)
3. Vectorize and store the data into LanceDB
4. Search semantically from LanceDB by AI as per the input/output templates
5. Save the above two templates/prompts and search results back to DB
6. Export the results as a report

## Phases

Save the result of each Phase to a markdown file.

### Phase 1: Import local PDF papers

- Select files by file input in form
  - Allow multiple selection
  - Allow selecting folders
- If the total number of papers is very large, split them into batches to process
- Format: PDF (will allow other formats in future versions)
- Track import status per paper in SQLite `papers` table

### Phase 2: Parse PDFs into texts and chunks

- Check the PDF before converting:
  - **Page-level scanned detection**: extract text per page via PyMuPDF; flag pages with < 50 characters as image-scanned
  - **Mixed PDFs**: extract text from pages that have it, flag scanned pages for future OCR
  - Skip entirely if > 50% of pages are image-only (mark as `skipped_ocr` in DB)
- Skip if file format is not PDF
- Use Python scripts NOT AI model at this phase

#### Chunking strategy

Two-tier hierarchical chunking with metadata preservation:

**Tier 1 — Section-level (coarse)**:
- Detect section headers via regex + font size/style heuristics: Abstract, Introduction, Method, Participants, Procedure, Results, Discussion, General Discussion, References, Acknowledgments
- For multi-study papers, detect sub-sections (e.g. "Study 1 Method", "Experiment 2 Participants")

**Tier 2 — Paragraph-level (fine)**:
- Within each section, split by paragraphs
- Target chunk size: 300-500 tokens with 50-token overlap
- Each chunk inherits section metadata from Tier 1

**Special handling**:
- Tables: extract as separate chunks tagged `is_table=true` (may exceed normal size)
- Figure captions: separate chunks with type metadata
- Supplementary materials: chunk separately, link via main paper's `doc_id`
- References section: chunk but deprioritize in search (lower weight or separate index)

**Metadata per chunk** (critical for citation tracking):
- `chunk_id`: composite key (e.g. `151_methods_p3_c2`)
- `doc_id`, `doc_title`, `authors`, `year`
- `section`: detected section name
- `study_label`: detected study label for multi-study papers
- `page_start`, `page_end`
- `paragraph_index`
- `char_offset_start`, `char_offset_end`
- `is_table`, `is_supplementary`

### Phase 3: Vectorize and store the data into LanceDB

- LanceDB runs embedded inside the Python sidecar (no external server)
- Embed chunks using SPECTER2 (local, 768-dim)
- Store vectors alongside all chunk metadata in LanceDB
- Incremental indexing: new papers added via `table.add()` without re-embedding existing ones

Storage estimates:
| Scale | Chunks | LanceDB Size | Embedding Time |
|-------|--------|-------------|----------------|
| 50 papers | ~2,000 | ~6MB | ~30s |
| 500 papers | ~20,000 | ~60MB | ~5min |
| 2,000 papers | ~80,000 | ~240MB | ~20min |

### Phase 4: Search semantically from LanceDB

#### Template setup

- User uploads input template in markdown format and enters prompts alongside to explain further requirements if any
  - The template may be a SKILL markdown file (see `doc/raw/SKILL.md` for example)
  - AI model parses both the template file and entered prompts
  - Any of input template and prompts may be empty but both cannot be empty at the same time
- User uploads output template
  - It may be in any format
  - AI model parses the output file to better match the input template

#### Template parsing (AI-assisted)

1. **Schema extraction**: Send template to Claude to extract structured JSON field definitions (field name, type, description, extraction rules, examples). Cache per template content hash.
2. **Output template parsing**: Similarly extract expected output fields and structure.

#### Field matching

Three-pass matching between input and output template fields:
1. **Exact match**: field names are identical
2. **Fuzzy match**: string similarity (Levenshtein distance)
3. **Semantic match**: Claude determines if an output field can be derived from input fields

Each output field classified as: Matched / Derivable / Unmatched / Ambiguous

- If there are Unmatched fields, list them in popup dialog and direct user to edit input template again until all are matched
  - Add `Ignore` option for users to skip mismatches
- **V1 scope**: Support SKILL-style structured markdown templates. Defer truly arbitrary format support.

#### Citation/provenance tracking

Each output field must reference its source location:
- Article title, page number(s), section, paragraph
- Direct quote from source text

Implementation:
- Provenance metadata established at chunking time (Phase 2) and stored in LanceDB alongside vectors
- Prompt Claude to cite `chunk_id` + verbatim quote for each extracted field
- Return citations as structured JSON per field

#### Search execution

When all settings are confirmed:
1. **Two-stage retrieval**: Vector search narrows to relevant chunks, then Claude extracts data from the subset
2. **Batch processing**: Process papers with 5-10 concurrent API calls (within rate limits)
3. **Caching**: Cache extraction results per (paper, template) pair — skip on re-runs
4. **Progressive display**: Show results as they arrive, not all at once
5. **Background queue**: Process in background with progress tracking; UI remains responsive

### Phase 5: Save templates/prompts and search results back to DB

- All data persisted in SQLite (templates, sessions, results, edit history)
- List page to show all stored search sessions and results
  - Allow user to re-search by one click (re-run same session config)
  - Allow user to edit result data before running a new search (edits tracked in `result_edits`)
  - Infinite-scroll pagination for large result sets (`LIMIT/OFFSET` or keyset pagination)

### Phase 6: Export the results as a report

- Format: .xlsx, .pdf, .md
- Allow multi-selection of results to export
- Libraries:
  - `.xlsx`: `openpyxl` (supports styling, multiple sheets, matches reference format)
  - `.pdf`: `weasyprint` (HTML-to-PDF with CSS styling)
  - `.md`: built-in string formatting + `tabulate` for tables

## App Updates

Leverage Tauri's built-in `tauri-plugin-updater` for auto-updates.

## Scalability Notes

| Scale | PDF Parse | Embedding | Search Latency | LLM Extraction |
|-------|-----------|-----------|----------------|----------------|
| 50 papers | ~30s | ~30s | <50ms | ~4min sequential |
| 500 papers | ~5min | ~5min | <100ms | ~40min (5x parallel) |
| 2,000 papers | ~20min | ~20min | <200ms | ~2.5hr (10x parallel) |

LLM extraction is the primary bottleneck. Mitigations: parallel API calls, result caching, two-stage retrieval, progressive display.
