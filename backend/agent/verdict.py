import re
from typing import Dict, Any


def format_verdict_display(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format verdict data for frontend display.
    """
    decision = (verdict.get("decision", "WATCH") or "WATCH").upper()
    reasoning = _clean_text(verdict.get("reasoning", ""))
    signals = [_clean_text(signal) for signal in verdict.get("signals", []) if _clean_text(signal)]

    return {
        "decision": decision,
        "reasoning": reasoning,
        "signals": signals,
        "color": _get_verdict_color(decision),
        "summary": _build_verdict_summary(decision, reasoning, signals),
    }


def _clean_text(value: Any) -> str:
    """Normalize whitespace and remove empty fragments."""
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _build_verdict_summary(decision: str, reasoning: str, signals: list[str]) -> str:
    """Build a compact, human-readable summary for the response."""
    signal_count = len(signals)
    preview = reasoning[:180] + ("..." if len(reasoning) > 180 else "")
    return f"Decision: {decision}. Signals: {signal_count}. {preview}".strip()


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
