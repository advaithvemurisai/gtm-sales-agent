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
    return Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
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


def run_web_search(client: Anthropic, query: str, logger: logging.Logger, operation: str) -> tuple[str, list[str]]:
    """Run a web search turn and return its text plus the cited source URLs."""
    # A timed-out search rarely succeeds on retry; fail fast and let the caller report the source as unavailable.
    search_client = client.with_options(timeout=SEARCH_TIMEOUT_SECONDS, max_retries=0)
    messages = [{"role": "user", "content": query}]
    content = []
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
        content.extend(response.content)
        if getattr(response, "stop_reason", None) != "pause_turn":
            break
        messages = [*messages, {"role": "assistant", "content": response.content}]

    text_blocks = [block for block in content if getattr(block, "type", None) == "text"]
    text = " ".join(block.text for block in text_blocks).strip()
    urls = [
        citation.url
        for block in text_blocks
        for citation in (getattr(block, "citations", None) or [])
        if getattr(citation, "url", None)
    ]
    return text, list(dict.fromkeys(urls))
