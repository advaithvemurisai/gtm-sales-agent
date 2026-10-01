"""In-process TTL cache for gathered evidence.

Evidence about a company doesn't depend on the seller's ICP, so re-running with edited criteria (or
looking up the same account again) can skip the web research and only regenerate the verdict.
"""
import copy
import threading
import time

EVIDENCE_TTL_SECONDS = 6 * 60 * 60
_MAX_ENTRIES = 256

_lock = threading.Lock()
_entries: dict[tuple, tuple[float, dict]] = {}


def cache_key(company_name: str, company_website: str | None) -> tuple[str, str]:
    website = (company_website or "").strip().lower()
    for prefix in ("https://", "http://", "www."):
        website = website.removeprefix(prefix)
    return " ".join(company_name.lower().split()), website.rstrip("/")


def get(key: tuple, now: float | None = None) -> dict | None:
    now = time.monotonic() if now is None else now
    with _lock:
        entry = _entries.get(key)
        if not entry:
            return None
        stored_at, evidence = entry
        if now - stored_at > EVIDENCE_TTL_SECONDS:
            del _entries[key]
            return None
        return copy.deepcopy(evidence)


def put(key: tuple, evidence: dict, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _lock:
        if len(_entries) >= _MAX_ENTRIES:
            oldest = min(_entries, key=lambda k: _entries[k][0])
            del _entries[oldest]
        _entries[key] = (now, copy.deepcopy(evidence))


def clear() -> None:
    with _lock:
        _entries.clear()
