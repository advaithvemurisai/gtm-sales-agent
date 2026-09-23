import pytest

from backend.agent.pipeline import _parse_verdict
from backend.agent.verdict import format_verdict_display


def test_parse_verdict_accepts_bold_sections_and_confidence():
    result = _parse_verdict(
        "**VERDICT:** PURSUE\n"
        "**REASONING:** Headcount matches the ICP and hiring is active.\n"
        "**KEY SIGNALS:**\n"
        "- **Hiring:** VP Engineering role is open.\n"
        "**CONFIDENCE:** HIGH"
    )

    assert result["decision"] == "PURSUE"
    assert result["reasoning"] == "Headcount matches the ICP and hiring is active."
    assert result["signals"] == ["Hiring: VP Engineering role is open."]
    assert result["confidence"] == "high"


def test_parse_verdict_rejects_missing_sections():
    with pytest.raises(ValueError, match="missing"):
        _parse_verdict("VERDICT: WATCH\nKEY SIGNALS:\n- Not enough evidence")


def test_format_verdict_display_defaults_confidence_to_unknown_or_given_value():
    result = format_verdict_display({
        "decision": "WATCH",
        "reasoning": "Evidence is mixed.",
        "signals": ["Hiring activity is unclear."],
        "confidence": "low",
    })

    assert result["confidence"] == "low"

@pytest.mark.parametrize("line, expected", [
    ("CONFIDENCE:", "unknown"),
    ("CONFIDENCE: Medium.", "medium"),
    ("CONFIDENCE: [HIGH]", "high"),
    ("Confidence: **High**", "high"),
    ("**CONFIDENCE:** Low - two sources failed", "low"),
])
def test_parse_verdict_reads_confidence_leniently(line, expected):
    result = _parse_verdict(
        "VERDICT: WATCH\nREASONING: Evidence is mixed.\nKEY SIGNALS:\n* Hiring is unclear\n" + line
    )

    assert result["confidence"] == expected
    assert result["signals"] == ["Hiring is unclear"]
