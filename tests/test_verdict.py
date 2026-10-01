from backend.agent.confidence import assess_coverage, cap_confidence
from backend.agent.verdict import format_verdict_display


def test_format_verdict_display_defaults_confidence_to_unknown_or_given_value():
    result = format_verdict_display({
        "decision": "WATCH",
        "reasoning": "Evidence is mixed.",
        "signals": ["Hiring activity is unclear."],
        "confidence": "low",
    })

    assert result["confidence"] == "low"


def test_format_verdict_display_has_no_canned_next_step():
    assert format_verdict_display({"decision": "PURSUE", "reasoning": "Strong fit."})["next_step"] == ""


def test_format_verdict_display_passes_criteria_and_note():
    result = format_verdict_display({
        "decision": "PURSUE",
        "reasoning": "Fit.",
        "criteria": [{"criterion": "Company size", "status": "met", "evidence": "120 employees"}],
        "confidence_note": "Confidence capped at medium: x.",
    })

    assert result["criteria"][0]["status"] == "met"
    assert result["confidence_note"].startswith("Confidence capped")


ICP = {"target_company_size": "50-500", "funding_stage": ["Series A"], "tech_signals": ["Salesforce"], "hiring_signals": ["RevOps"]}
GOOD_TECH = {"technologies": {"crm_sales": ["Salesforce"]}}
GOOD_HIRING = {"open_positions": ["RevOps Lead"]}
GOOD_WEB = {"company_signals": {"headcount_range": "51-200", "funding_stage": "Series A"}}


def test_full_coverage_leaves_confidence_alone():
    coverage = assess_coverage(ICP, GOOD_TECH, GOOD_HIRING, GOOD_WEB)

    assert cap_confidence("high", coverage) == ("high", None)


def test_one_failed_source_caps_at_medium():
    coverage = assess_coverage(ICP, {"error": "timeout"}, GOOD_HIRING, GOOD_WEB)
    confidence, note = cap_confidence("high", coverage)

    assert confidence == "medium"
    assert "technology" in note


def test_two_failed_sources_cap_at_low():
    coverage = assess_coverage(ICP, {"error": "x"}, {"error": "y"}, GOOD_WEB)

    assert cap_confidence("high", coverage)[0] == "low"
    assert cap_confidence("low", coverage) == ("low", None)


def test_news_failure_alone_counts_one_source():
    web = {**GOOD_WEB, "news_error": "timeout"}
    coverage = assess_coverage(ICP, GOOD_TECH, GOOD_HIRING, web)

    assert coverage["failed_sources"] == ["recent news"]


def test_missing_evidence_for_specified_criteria_caps_confidence():
    coverage = assess_coverage(ICP, {"technologies": {}}, {"open_positions": []}, {"company_signals": {}})

    assert coverage["evidence_gaps"] == ["company size", "funding stage", "technology", "hiring roles"]
    assert cap_confidence("high", coverage)[0] == "low"


def test_unspecified_criteria_are_not_gaps():
    coverage = assess_coverage({}, {"technologies": {}}, {"open_positions": []}, {"company_signals": {}})

    assert coverage["evidence_gaps"] == []
