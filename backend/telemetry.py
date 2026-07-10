import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator


def _usage_value(usage: Any, key: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return usage.get(key) or 0
    return getattr(usage, key, 0) or 0


def log_anthropic_usage(
    logger: logging.Logger,
    *,
    operation: str,
    model: str,
    started_at: float,
    response: Any,
) -> None:
    usage = getattr(response, "usage", None)
    input_tokens = _usage_value(usage, "input_tokens")
    output_tokens = _usage_value(usage, "output_tokens")
    cache_creation_input_tokens = _usage_value(usage, "cache_creation_input_tokens")
    cache_read_input_tokens = _usage_value(usage, "cache_read_input_tokens")
    duration_ms = (time.perf_counter() - started_at) * 1000
    total_tokens = (
        input_tokens
        + output_tokens
        + cache_creation_input_tokens
        + cache_read_input_tokens
    )

    logger.info(
        "LLM call completed operation=%s model=%s duration_ms=%.1f "
        "input_tokens=%s output_tokens=%s cache_creation_input_tokens=%s "
        "cache_read_input_tokens=%s total_tokens=%s",
        operation,
        model,
        duration_ms,
        input_tokens,
        output_tokens,
        cache_creation_input_tokens,
        cache_read_input_tokens,
        total_tokens,
    )


@contextmanager
def timed_operation(logger: logging.Logger, operation: str, **fields: Any) -> Iterator[None]:
    started_at = time.perf_counter()
    logger.info(
        "Operation started operation=%s %s",
        operation,
        _format_fields(fields),
    )
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "Operation completed operation=%s duration_ms=%.1f %s",
            operation,
            duration_ms,
            _format_fields(fields),
        )


def _format_fields(fields: dict[str, Any]) -> str:
    return " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
