# ASCI-Desktop

An academic tool for researchers to import, parse, and analyze research papers. Extract structured data using AI via custom templates, store results in a vector database, and export reports.

## Stack

- **Desktop**: Tauri v2 (Rust shell)
- **Frontend**: React + Tailwind CSS + TypeScript
- **Backend**: Python 3.11+ (FastAPI, runs as Tauri sidecar)
- **AI**: Claude Code CLI (`claude -p`)
- **Embedding**: ONNX Runtime + all-MiniLM-L6-v2 (384-dim, ~88 MB)
- **Vector DB**: LanceDB (embedded, no server)
- **Relational DB**: SQLite
- **PDF Parsing**: PyMuPDF + pdfplumber
- **Export**: openpyxl (.xlsx), weasyprint (.pdf), Markdown (.md)

## Quick Start

### Prerequisites

- Node.js 22+
- Rust (install via `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- Python 3.11+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

### Setup

```bash
# Install frontend dependencies
npm install

# Set up Python backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
```

### Run

```bash
npm run tauri dev
```

The Tauri app automatically starts the Python backend (port 8765) on launch and stops it on exit — no separate terminal needed. A status indicator in the header shows backend connection state.

To run the backend manually (e.g. for debugging):

```bash
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --port 8765
```

## Workflow (6 Phases)

### Phase 1: Import
- Native file picker dialog for selecting multiple PDF files
- Supports bulk import with deduplication
- Tracks import status per paper in SQLite
- Auto-navigates to Parse phase after import

### Phase 2: Parse
- Extracts text from PDFs using PyMuPDF
- Detects image-scanned pages (< 50 chars) and skips mostly-scanned PDFs
- Auto-navigates to Vectorize phase when all papers are parsed
- Two-tier hierarchical chunking:
  - **Section-level**: Detects academic headers (Abstract, Method, Results, etc.)
  - **Paragraph-level**: 300-500 token chunks with 50-token overlap
- Preserves metadata per chunk: section, page numbers, paragraph index, character offsets

### Phase 3: Vectorize
- Embeds chunks using ONNX Runtime (all-MiniLM-L6-v2, no PyTorch dependency)
- Stores vectors + metadata in LanceDB (embedded, no server)
- Incremental indexing (new papers added without re-embedding)

### Phase 4: Search & Extract
- Upload input/output templates (markdown format, e.g., SKILL files)
- Enter additional prompts for context
- Two-stage retrieval: vector search narrows to relevant chunks, then Claude extracts structured fields
- Each extracted field includes citation provenance (chunk ID, page, section, quote)

### Phase 5: Results
- Browse search sessions and results
- Inline field editing with full edit history
- Session filtering and infinite-scroll pagination

### Phase 6: Export
- Multi-format export: `.xlsx`, `.pdf`, `.md`
- Multi-selection of formats for batch download
- Session-scoped or global export

## Project Structure

```
ASCI-desktop/
├── src/                          # React + Tailwind frontend
│   ├── App.tsx                   # Main app with phase navigation
│   ├── api.ts                    # API client
│   ├── styles.css                # Tailwind entry
│   └── components/
│       ├── ImportPanel.tsx        # Phase 1: PDF import
│       ├── ParsePanel.tsx         # Phase 2: Parse status
│       ├── VectorizePanel.tsx     # Phase 3: Vectorize
│       ├── SearchPanel.tsx        # Phase 4: Template + AI search
│       ├── ResultsPanel.tsx       # Phase 5: Results list + inline edit
│       └── ExportPanel.tsx        # Phase 6: Multi-format export
├── src-tauri/                    # Tauri v2 Rust shell
│   ├── src/lib.rs                # Auto-launches Python backend, kills on exit
│   └── Cargo.toml
├── backend/                      # Python FastAPI backend
│   ├── pyproject.toml
│   └── app/
│       ├── main.py               # FastAPI app (4 routers, 23 endpoints)
│       ├── config.py             # OS-specific data directories
│       ├── database.py           # SQLite schema (5 tables)
│       ├── routers/
│       │   ├── papers.py         # Import, parse, vectorize
│       │   ├── search.py         # Templates, AI search execution
│       │   ├── results.py        # Sessions, results, edit history
│       │   └── export.py         # xlsx/pdf/md export
│       └── services/
│           ├── pdf_parser.py     # PyMuPDF extraction + chunking
│           ├── vectorstore.py    # LanceDB + embeddings
│           ├── ai_service.py     # Claude CLI (claude -p)
│           └── exporter.py       # openpyxl, weasyprint, markdown
└── doc/                          # Design docs + sample data
    ├── draft.md                  # Architecture specification
    └── raw/                      # Sample PDFs and templates
```

## Data Storage

All data is stored in the OS app data directory:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/ASCI-Desktop/` |
| Windows | `%APPDATA%/ASCI-Desktop/` |
| Linux | `~/.local/share/ASCI-Desktop/` |

- **LanceDB**: Vector embeddings + chunk metadata
- **SQLite**: Papers, templates, search sessions, results, edit history

Backup: copy the entire directory.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health check |
| POST | `/papers/import` | Import PDFs from paths |
| GET | `/papers/` | List papers |
| GET | `/papers/count` | Paper counts by status |
| DELETE | `/papers/{id}` | Remove a paper |
| POST | `/papers/parse` | Parse pending PDFs |
| POST | `/papers/vectorize` | Vectorize parsed papers |
| GET | `/papers/vector-count` | Total chunks in LanceDB |
| POST | `/search/templates` | Upload template |
| GET | `/search/templates` | List templates |
| GET | `/search/ai-status` | Check Claude CLI availability |
| POST | `/search/execute` | Run AI search |
| GET | `/results/sessions` | List search sessions |
| GET | `/results/` | List results |
| PUT | `/results/{id}` | Edit a result field |
| POST | `/export/` | Export results (xlsx/pdf/md) |

## Design Document

See [`doc/draft.md`](doc/draft.md) for the full architecture specification including data schemas, chunking strategy, scalability estimates, and AI service design.
