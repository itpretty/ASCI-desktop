"""AI service using Claude Code CLI (claude -p).

Uses Claude Code Team account on top priority.
Falls back to API key if Team account is unavailable.
"""

import json
import shutil
import subprocess


def _find_claude_cli() -> str | None:
    """Find the claude CLI binary."""
    return shutil.which("claude")


def is_available() -> bool:
    """Check if Claude CLI is available."""
    return _find_claude_cli() is not None


def check_status() -> dict:
    """Check Claude CLI availability."""
    cli = _find_claude_cli()
    if not cli:
        return {
            "available": False,
            "error": "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code",
        }
    return {"available": True, "error": None}


def query(prompt: str, system: str | None = None, max_tokens: int = 4096) -> str:
    """Send a prompt to Claude via `claude -p` and return the response text."""
    cli = _find_claude_cli()
    if not cli:
        raise RuntimeError(
            "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code"
        )

    # Strip null bytes that may come from PDF extraction
    prompt = prompt.replace("\x00", "")
    cmd = [cli, "-p", prompt, "--output-format", "text"]
    if system:
        cmd.extend(["--system-prompt", system])

    # Use inherited env but remove ANTHROPIC_API_KEY so the CLI
    # prefers the Team account (OAuth/keychain) over API key auth.
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )

    output = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        error_msg = stderr or output or "Unknown error"
        raise RuntimeError(f"Claude CLI error: {error_msg[:300]}")

    if not output:
        raise RuntimeError("Claude CLI returned empty response")

    return output


def extract_fields_from_chunks(
    chunks: list[dict],
    template_text: str,
    prompt_text: str,
    doc_title: str,
) -> dict:
    """Use Claude to extract structured fields from retrieved chunks.

    Returns a dict with 'fields' (extracted data) and 'citations' (provenance).
    """
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

    response = query(user_prompt, system=system)

    # Try to parse JSON from response
    try:
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
