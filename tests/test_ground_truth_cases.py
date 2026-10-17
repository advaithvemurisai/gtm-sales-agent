"""Offline checks for the ground-truth eval cases: the coverage cap is deterministic, so every case's
expected failed sources, evidence gaps and confidence ceiling must match the code exactly."""

import pytest

from backend.agent.confidence import assess_coverage, cap_confidence
from backend.agent.criteria import criterion_key, specified_keys
from scripts.eval_ground_truth import build_evidence, build_icp, load_cases, score_verdict

SPEC = load_cases()
CASES = SPEC["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case):
    icp = build_icp(SPEC, case)
    acceptable = case.get("acceptable", [case["expected"]])

    assert case["expected"] in acceptable
    assert set(acceptable) <= {"PURSUE", "WATCH", "DEPRIORITIZE"}
    assert bool(case.get("boundary")) == (len(acceptable) > 1)
    assert set(case["criteria"]) == set(specified_keys(icp))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_coverage_matches_ground_truth(case):
    evidence = build_evidence(case)
    coverage = assess_coverage(
        build_icp(SPEC, case),
        evidence["technology"]["raw_data"],
        evidence["hiring"]["raw_data"],
        evidence["web_search"]["raw_data"],
    )

    assert coverage == case["coverage"]
    assert cap_confidence("high", coverage)[0] == case["coverage"]["ceiling"]


@pytest.mark.parametrize("name,key", [
    ("Company size", "size"), ("Headcount", "size"), ("Funding stage", "funding"),
    ("Technology", "technology"), ("Tech stack", "technology"), ("Hiring roles", "hiring"),
    ("Budget", "budget"), ("Budget (revenue)", "budget"), ("Location", None),
])
def test_criterion_names_map_to_icp_keys(name, key):
    assert criterion_key(name) == key


def test_scorer_flags_failure_read_as_negative_evidence():
    case = next(c for c in CASES if c["id"] == "GT05")
    icp = build_icp(SPEC, case)
    verdict = {
        "decision": "DEPRIORITIZE", "confidence": "low", "model_confidence": "medium", "reasoning": "",
        "coverage": case["coverage"],
        "criteria": [
            {"criterion": "Company size", "status": "met", "source_ids": [1]},
            {"criterion": "Funding stage", "status": "met", "source_ids": [1]},
            {"criterion": "Technology", "status": "not_met", "source_ids": []},
            {"criterion": "Hiring roles", "status": "unknown", "source_ids": []},
            {"criterion": "Budget", "status": "met", "source_ids": [1]},
            {"criterion": "Location", "status": "not_met", "source_ids": []},
        ],
    }

    score = score_verdict(case, icp, verdict)

    assert not score["acceptable"]
    assert score["criteria_misses"] == ["technology: not_met (want unknown)"]
    assert score["criteria_correct"] == 4
    assert score["cited"] == 3 and score["cited_total"] == 5
    assert score["coverage_exact"]


def test_scorer_flags_unspecified_criterion_marked_not_met():
    case = next(c for c in CASES if c["id"] == "GT15")
    verdict = {
        "decision": "WATCH", "confidence": "high", "model_confidence": "high", "reasoning": "",
        "coverage": case["coverage"],
        "criteria": [
            {"criterion": "Company size", "status": "met", "source_ids": [1]},
            {"criterion": "Hiring roles", "status": "not_met", "source_ids": []},
        ],
    }

    score = score_verdict(case, build_icp(SPEC, case), verdict)

    assert score["acceptable"] and not score["strict"]
    assert score["spurious_not_met"] == ["hiring"]
