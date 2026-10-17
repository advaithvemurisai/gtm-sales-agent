from backend.agent import evidence_cache
from backend.agent.criteria import missing_criteria, repair_criteria
from backend.agent.pipeline import run_evaluation_pipeline

ICP = {"target_company_size": "51-500", "funding_stage": ["Series A"], "tech_signals": ["NetSuite"],
       "hiring_signals": ["Controller"], "budget_indicator": "mid-market"}
FULL = [{"criterion": name, "status": "met", "evidence": "x", "source_ids": [1]}
        for name in ("Company size", "Funding stage", "Technology", "Hiring roles", "Budget")]
TRUNCATED = [{"criterion": "Company size", "status": "met", "evidence": "x", "source_ids": [1]},
             {"criterion": "placeholder", "status": "unknown", "evidence": "", "source_ids": []}]


def test_complete_scorecard_has_nothing_missing():
    assert missing_criteria({"criteria": FULL}, ICP) == []


def test_truncated_scorecard_is_detected():
    assert missing_criteria({"criteria": TRUNCATED}, ICP) == ["funding", "technology", "hiring", "budget", "unnamed"]


def test_extra_named_row_is_not_malformed():
    extra = [*FULL, {"criterion": "Competitor", "status": "not_met", "evidence": "x", "source_ids": []}]
    assert missing_criteria({"criteria": extra}, ICP) == []


def test_unspecified_fields_are_not_required():
    assert missing_criteria({"criteria": FULL[:1]}, {"target_company_size": "11-200", "funding_stage": []}) == []


def test_repair_drops_placeholder_and_fills_unknowns():
    verdict = {"criteria": list(TRUNCATED)}
    repair_criteria(verdict, ICP)

    assert [c["criterion"] for c in verdict["criteria"]] == ["Company size", "Funding stage", "Technology", "Hiring roles", "Budget"]
    assert all(c["status"] == "unknown" for c in verdict["criteria"][1:])


def _evidence():
    return {
        "technology": {"raw_data": {"technologies": {"other": ["NetSuite"]}, "source_urls": ["https://a"]}, "summary": ""},
        "hiring": {"raw_data": {"open_positions": ["Controller"], "source_urls": []}, "summary": ""},
        "web_search": {"raw_data": {"company_signals": {"funding_stage": "Series A", "headcount_range": "51-200",
                                                         "revenue_estimate": "$10M"}, "source_urls": []}, "summary": ""},
    }


def _verdict(criteria):
    return {"decision": "PURSUE", "confidence": "high", "reasoning": "r", "signals": [], "next_step": "n", "criteria": criteria}


def _run(monkeypatch, responses):
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(1)
        return _verdict([dict(c) for c in responses[len(calls) - 1]])

    monkeypatch.setattr("backend.agent.pipeline._generate_verdict", fake_generate)
    evidence_cache.clear()
    evidence_cache.put(evidence_cache.cache_key("Acme", None), _evidence())
    return run_evaluation_pipeline("Acme", ICP), calls


def test_pipeline_retries_truncated_scorecard(monkeypatch):
    result, calls = _run(monkeypatch, [TRUNCATED, FULL])

    assert len(calls) == 2
    assert [c["status"] for c in result["verdict"]["criteria"]] == ["met"] * 5


def test_pipeline_repairs_when_retry_is_also_truncated(monkeypatch):
    result, calls = _run(monkeypatch, [TRUNCATED, TRUNCATED])

    assert len(calls) == 2
    assert len(result["verdict"]["criteria"]) == 5
    assert "placeholder" not in [c["criterion"] for c in result["verdict"]["criteria"]]


def test_pipeline_does_not_retry_complete_scorecard(monkeypatch):
    _, calls = _run(monkeypatch, [FULL])

    assert len(calls) == 1
