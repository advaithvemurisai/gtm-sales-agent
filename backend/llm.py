import json
import logging
import os
import time
from typing import Any

from anthropic import Anthropic

from backend.config import MAX_RETRIES, REQUEST_TIMEOUT_SECONDS, SEARCH_TIMEOUT_SECONDS, SONNET_MODEL, WEB_SEARCH_TOOL
from backend.telemetry import log_anthropic_usage

# Server-side web search can pause a long turn; resume it a bounded number of times.
_MAX_SEARCH_CONTINUATIONS = 3


def get_client() -> Anthropic:
    # User-scoped keys (sk-ant-usr-...) aren't tied to a workspace, so the API needs it named.
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    return Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
        default_headers={"anthropic-workspace-id": workspace_id} if workspace_id else None,
    )


def load_prompt(prompt_file: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", prompt_file)
    with open(prompt_path, "r") as f:
        return f.read()


def response_text(response: Any) -> str:
    """Join the text blocks of a response, skipping thinking and tool blocks."""
    return "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()


def parse_json_object(text: str) -> dict:
    """Parse a JSON object from model output that may be wrapped in code fences."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def generate_json(
    client: Anthropic,
    *,
    model: str,
    prompt: str,
    schema: dict,
    operation: str,
    logger: logging.Logger,
    system: str | None = None,
    max_tokens: int = 1024,
    effort: str | None = None,
) -> dict:
    """Call the model with a JSON-schema output format and return the parsed object.

    The schema is enforced by the API (structured outputs), so there is no fence stripping or
    best-effort parsing. Raises if the model refuses, is cut off, or returns invalid JSON, so callers
    can report the source as failed instead of treating a bad parse as real evidence.
    """
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if effort:
        output_config["effort"] = effort
    kwargs: dict = {"system": system} if system else {}
    started_at = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        output_config=output_config,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    log_anthropic_usage(logger, operation=operation, model=model, started_at=started_at, response=response)
    if getattr(response, "stop_reason", None) in ("refusal", "max_tokens"):
        raise ValueError(f"{operation} returned no usable output (stop_reason={response.stop_reason})")
    return parse_json_object(response_text(response))


def _join_text(content: list) -> str:
    """Join text blocks as written. Search answers split text at every citation, so adjacent blocks are
    fragments of one passage and join directly; text separated by a search call starts a new paragraph."""
    parts: list[str] = []
    after_other_block = False
    for block in content:
        if getattr(block, "type", None) != "text":
            after_other_block = bool(parts)
            continue
        if after_other_block:
            parts.append("\n\n")
            after_other_block = False
        parts.append(block.text)
    return "".join(parts).strip()


def run_web_search(client: Anthropic, query: str, logger: logging.Logger, operation: str) -> tuple[str, list[str]]:
    """Run a web search turn and return its text plus the cited source URLs."""
    # A timed-out search rarely succeeds on retry; fail fast and let the caller report the source as unavailable.
    search_client = client.with_options(timeout=SEARCH_TIMEOUT_SECONDS, max_retries=0)
    messages = [{"role": "user", "content": query}]
    turns: list[list] = []
    for _ in range(_MAX_SEARCH_CONTINUATIONS + 1):
        started_at = time.perf_counter()
        response = search_client.messages.create(
            model=SONNET_MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )
        log_anthropic_usage(logger, operation=operation, model=SONNET_MODEL, started_at=started_at, response=response)
        turns.append(list(response.content))
        if getattr(response, "stop_reason", None) != "pause_turn":
            break
        messages = [*messages, {"role": "assistant", "content": response.content}]

    # A paused turn resumes after a search call, so each response's text starts a new paragraph.
    text = "\n\n".join(part for part in (_join_text(turn) for turn in turns) if part)
    text_blocks = [block for turn in turns for block in turn if getattr(block, "type", None) == "text"]
    urls = [
        citation.url
        for block in text_blocks
        for citation in (getattr(block, "citations", None) or [])
        if getattr(citation, "url", None)
    ]
    return text, list(dict.fromkeys(urls))
