import re
from typing import Dict, Any


def format_verdict_display(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format verdict data for frontend display.
    """
    decision = (verdict.get("decision", "WATCH") or "WATCH").upper()
    reasoning = _clean_text(verdict.get("reasoning", ""))
    signals = [_signal(signal) for signal in verdict.get("signals", [])]
    signals = [signal for signal in signals if signal["text"]]

    return {
        "decision": decision,
        "reasoning": reasoning,
        "signals": signals,
        "color": _get_verdict_color(decision),
        "confidence": _clean_text(verdict.get("confidence", "unknown")).lower() or "unknown",
        "next_step": _clean_text(verdict.get("next_step")),
        "confidence_note": _clean_text(verdict.get("confidence_note")),
        "criteria": [
            {**{key: _clean_text(item.get(key)) for key in ("criterion", "status", "evidence")},
             "source_ids": _source_ids(item)}
            for item in verdict.get("criteria") or []
        ],
    }


def _source_ids(item: Any) -> list:
    return list(item.get("source_ids") or []) if isinstance(item, dict) else []


def _signal(signal: Any) -> Dict[str, Any]:
    """Signals are {text, source_ids}; accept a bare string too (older saved results)."""
    text = signal.get("text") if isinstance(signal, dict) else signal
    return {"text": _clean_text(text), "source_ids": _source_ids(signal)}


def _clean_text(value: Any) -> str:
    """Normalize whitespace and remove empty fragments."""
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _get_verdict_color(decision: str) -> str:
    """
    Return color coding for verdict display.
    """
    decision_upper = decision.upper()
    if decision_upper == "PURSUE":
        return "green"
    elif decision_upper == "DEPRIORITIZE":
        return "red"
    else:
        return "yellow"

