"""AI service using Claude Code CLI (claude -p)."""

import json
import shutil
import subprocess


def _find_claude_cli() -> str | None:
    """Find the claude CLI binary."""
    return shutil.which("claude")


def is_available() -> bool:
    """Check if Claude CLI is available."""
    return _find_claude_cli() is not None


def query(prompt: str, system: str | None = None, max_tokens: int = 4096) -> str:
    """Send a prompt to Claude via `claude -p` and return the response text."""
    cli = _find_claude_cli()
    if not cli:
        raise RuntimeError(
            "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code"
        )

    cmd = [cli, "-p", prompt, "--output-format", "text"]
    if system:
        cmd.extend(["--system-prompt", system])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Claude CLI error: {stderr}")

    return result.stdout.strip()


def extract_fields_from_chunks(
    chunks: list[dict],
    template_text: str,
    prompt_text: str,
    doc_title: str,
) -> dict:
    """Use Claude to extract structured fields from retrieved chunks.

    Returns a dict with 'fields' (extracted data) and 'citations' (provenance).
    """
    # Build context from chunks
    context_parts = []
    for c in chunks:
        context_parts.append(
            f"[Chunk {c['chunk_id']}] Section: {c['section']}, "
            f"Pages {c['page_start']}-{c['page_end']}:\n{c['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    system = (
        "You are an academic research data extractor. "
        "Extract structured data from research paper chunks following the provided template. "
        "For each field you extract, cite the chunk_id and include a brief verbatim quote. "
        "Return your response as valid JSON with two keys: "
        '"fields" (object mapping field names to extracted values) and '
        '"citations" (object mapping field names to {chunk_id, quote}). '
        "If a field cannot be determined from the chunks, set its value to null."
    )

    user_prompt = f"""Paper: {doc_title}

Template/Instructions:
{template_text}

{f"Additional instructions: {prompt_text}" if prompt_text else ""}

Paper chunks:
{context}

Extract all fields defined in the template from the chunks above. Return valid JSON."""

    response = query(user_prompt, system=system, max_tokens=max_tokens)

    # Try to parse JSON from response
    try:
        # Find JSON in the response (it may be wrapped in markdown code blocks)
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        result = json.loads(json_str.strip())
        if "fields" not in result:
            result = {"fields": result, "citations": {}}
        return result
    except (json.JSONDecodeError, IndexError):
        return {
            "fields": {"raw_response": response},
            "citations": {},
        }


def parse_template(template_text: str) -> list[dict]:
    """Use Claude to extract field definitions from a template.

    Returns a list of {name, type, description} dicts.
    """
    system = (
        "You are a template parser. Extract field definitions from the given template. "
        "Return valid JSON: a list of objects with keys: name, type, description."
    )

    prompt = f"""Parse the following template and extract all field definitions:

{template_text}

Return a JSON array of field definitions."""

    response = query(prompt, system=system)

    try:
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        return json.loads(json_str.strip())
    except (json.JSONDecodeError, IndexError):
        return []
