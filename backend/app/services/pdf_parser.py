"""PDF text extraction and chunking with PyMuPDF."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


MIN_TEXT_PER_PAGE = 50  # characters to consider a page as having text
SCANNED_THRESHOLD = 0.5  # if > 50% pages are image-only, mark as scanned

# Common academic section headers
SECTION_PATTERNS = [
    re.compile(
        r"^(abstract|introduction|background|literature\s+review|"
        r"method(?:s|ology)?|participants?|procedure|measures?|materials?|"
        r"results?|findings|discussion|general\s+discussion|"
        r"conclusion|limitations|references?|acknowledgments?|"
        r"appendix|supplementary|funding)"
        r"(?:\s|$)",
        re.IGNORECASE,
    ),
    # Study/Experiment headers: "Study 1", "Experiment 2a"
    re.compile(
        r"^(?:study|experiment|exp\.?)\s+\d+[a-z]?\b", re.IGNORECASE
    ),
]

TARGET_CHUNK_TOKENS = 400
MAX_CHUNK_TOKENS = 600
OVERLAP_TOKENS = 50
APPROX_CHARS_PER_TOKEN = 4  # rough approximation


@dataclass
class PageText:
    page_num: int  # 0-indexed
    text: str
    is_scanned: bool


@dataclass
class Section:
    name: str
    start_page: int
    paragraphs: list[str] = field(default_factory=list)
    page_ranges: list[int] = field(default_factory=list)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    section: str
    study_label: str
    page_start: int
    page_end: int
    paragraph_index: int
    char_offset_start: int
    char_offset_end: int
    is_table: bool
    is_supplementary: bool


@dataclass
class ParseResult:
    doc_id: str
    title: str
    authors: str
    year: int | None
    page_count: int
    scanned_pages: list[int]
    is_mostly_scanned: bool
    chunks: list[Chunk]
    full_text: str


def extract_pages(pdf_path: Path) -> list[PageText]:
    """Extract text from each page, detecting scanned pages."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        is_scanned = len(text.strip()) < MIN_TEXT_PER_PAGE
        pages.append(PageText(page_num=page_num, text=text, is_scanned=is_scanned))
    doc.close()
    return pages


def extract_doc_id(filename: str) -> str:
    """Extract numeric ID from filename like '151-Some Title.pdf'."""
    match = re.match(r"^(\d+)", filename)
    return match.group(1) if match else filename.rsplit(".", 1)[0]


def _detect_section(line: str) -> str | None:
    """Check if a line is a section header."""
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return None
    for pattern in SECTION_PATTERNS:
        if pattern.match(stripped):
            return stripped
    return None


def _detect_study_label(section_name: str) -> str:
    """Extract study label from section name."""
    m = re.match(
        r"((?:study|experiment|exp\.?)\s+\d+[a-z]?)", section_name, re.IGNORECASE
    )
    return m.group(1) if m else ""


def _split_into_sections(pages: list[PageText]) -> list[Section]:
    """Split page text into sections based on header detection."""
    sections: list[Section] = []
    current = Section(name="preamble", start_page=0)

    for page in pages:
        if page.is_scanned:
            continue
        lines = page.text.split("\n")
        page_paragraphs: list[str] = []
        current_para = []

        for line in lines:
            section_name = _detect_section(line)
            if section_name:
                # Save accumulated paragraph
                if current_para:
                    para_text = " ".join(current_para).strip()
                    if para_text:
                        current.paragraphs.append(para_text)
                        if page.page_num not in current.page_ranges:
                            current.page_ranges.append(page.page_num)
                    current_para = []
                # Start new section
                if current.paragraphs or current.name != "preamble":
                    sections.append(current)
                current = Section(name=section_name, start_page=page.page_num)
            elif line.strip():
                current_para.append(line.strip())
            else:
                # Empty line = paragraph break
                if current_para:
                    para_text = " ".join(current_para).strip()
                    if para_text:
                        current.paragraphs.append(para_text)
                        if page.page_num not in current.page_ranges:
                            current.page_ranges.append(page.page_num)
                    current_para = []

        # End of page
        if current_para:
            para_text = " ".join(current_para).strip()
            if para_text:
                current.paragraphs.append(para_text)
                if page.page_num not in current.page_ranges:
                    current.page_ranges.append(page.page_num)
            current_para = []

    if current.paragraphs:
        sections.append(current)

    return sections


def _chunk_text(text: str, target_chars: int, max_chars: int) -> list[str]:
    """Split text into chunks of approximately target size."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_len + sentence_len > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Overlap: keep last sentence
            overlap = current_chunk[-1:] if current_chunk else []
            current_chunk = overlap
            current_len = sum(len(s) for s in current_chunk)
        current_chunk.append(sentence)
        current_len += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def parse_pdf(pdf_path: Path, is_supplementary: bool = False) -> ParseResult:
    """Parse a PDF into structured chunks with metadata."""
    filename = pdf_path.name
    doc_id = extract_doc_id(filename)
    pages = extract_pages(pdf_path)

    page_count = len(pages)
    scanned_pages = [p.page_num for p in pages if p.is_scanned]
    scanned_ratio = len(scanned_pages) / max(page_count, 1)
    is_mostly_scanned = scanned_ratio > SCANNED_THRESHOLD

    # Build full text from non-scanned pages
    full_text = "\n\n".join(p.text for p in pages if not p.is_scanned)

    # Extract basic metadata from first page
    title = ""
    authors = ""
    year = None
    if pages and not pages[0].is_scanned:
        first_lines = pages[0].text.strip().split("\n")
        if first_lines:
            title = first_lines[0].strip()[:200]
        # Try to find year
        year_match = re.search(r"\b(19|20)\d{2}\b", pages[0].text)
        if year_match:
            year = int(year_match.group())

    if is_mostly_scanned:
        return ParseResult(
            doc_id=doc_id,
            title=title,
            authors=authors,
            year=year,
            page_count=page_count,
            scanned_pages=scanned_pages,
            is_mostly_scanned=True,
            chunks=[],
            full_text=full_text,
        )

    # Split into sections and chunk
    sections = _split_into_sections(pages)
    chunks: list[Chunk] = []
    char_offset = 0
    chunk_counter = 0

    target_chars = TARGET_CHUNK_TOKENS * APPROX_CHARS_PER_TOKEN
    max_chars = MAX_CHUNK_TOKENS * APPROX_CHARS_PER_TOKEN

    for section in sections:
        study_label = _detect_study_label(section.name)
        section_name = section.name.lower().strip()

        for para_idx, paragraph in enumerate(section.paragraphs):
            text_chunks = _chunk_text(paragraph, target_chars, max_chars)

            for chunk_text in text_chunks:
                chunk_counter += 1
                page_start = section.page_ranges[0] if section.page_ranges else 0
                page_end = section.page_ranges[-1] if section.page_ranges else 0

                chunk = Chunk(
                    chunk_id=f"{doc_id}_{section_name[:20]}_{para_idx}_{chunk_counter}",
                    doc_id=doc_id,
                    text=chunk_text,
                    section=section.name,
                    study_label=study_label,
                    page_start=page_start,
                    page_end=page_end,
                    paragraph_index=para_idx,
                    char_offset_start=char_offset,
                    char_offset_end=char_offset + len(chunk_text),
                    is_table=False,
                    is_supplementary=is_supplementary,
                )
                chunks.append(chunk)
                char_offset += len(chunk_text)

    return ParseResult(
        doc_id=doc_id,
        title=title,
        authors=authors,
        year=year,
        page_count=page_count,
        scanned_pages=scanned_pages,
        is_mostly_scanned=False,
        chunks=chunks,
        full_text=full_text,
    )
