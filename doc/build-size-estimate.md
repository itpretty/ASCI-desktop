# Build Size Estimate

## Current Stack (ONNX Runtime)

| Component | Estimated Size |
|-----------|---------------|
| Tauri shell (Rust binary) | ~10-15 MB |
| Frontend (React + Tailwind JS/CSS) | ~2-3 MB |
| Python backend (all dependencies) | ~150-200 MB |
| — ONNX Runtime | ~30 MB |
| — ONNX model (all-MiniLM-L6-v2) | ~88 MB |
| — LanceDB + PyArrow | ~100-150 MB |
| — PyMuPDF, weasyprint, tokenizers, etc. | ~50 MB |
| **Total (uncompressed)** | **~250-350 MB** |

Compared to the previous sentence-transformers/PyTorch stack (~800 MB - 1.2 GB), the ONNX approach is ~3-4x smaller.

## Previous Stack (sentence-transformers + PyTorch)

| Component | Estimated Size |
|-----------|---------------|
| PyTorch | ~500-600 MB |
| sentence-transformers + models | ~100-200 MB |
| Everything else | ~100-200 MB |
| **Total** | **~800 MB - 1.2 GB** |

## Verification

- ONNX model produces identical embeddings (cosine similarity = 1.000000 vs sentence-transformers)
- Full pipeline tested: 46 papers → 4,944 vector chunks, 0 errors
- Semantic search returns relevant results

## Further Optimization Options

### Option A: Use an embedding API (Voyage AI, OpenAI)
- Eliminates ONNX model + runtime entirely (~120 MB savings)
- Requires internet (already needed for Claude CLI)
- **Estimated total: ~80-100 MB**

### Option B: Move embeddings to Rust (candle / ort crate)
- Eliminates Python ML dependencies
- **Estimated total: ~80-100 MB**
- Requires significant Rust refactoring
