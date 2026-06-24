from typing import Dict, Any


def format_verdict_display(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format verdict data for frontend display.
    """
    return {
        "decision": verdict.get("decision", "WATCH"),
        "reasoning": verdict.get("reasoning", ""),
        "signals": verdict.get("signals", []),
        "color": _get_verdict_color(verdict.get("decision", "WATCH"))
    }


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
