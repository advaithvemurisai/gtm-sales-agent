"""Evaluate the verdict step against controlled-evidence cases with known answers.

Run from the repo root: python scripts/eval_ground_truth.py [--runs 3] [--only GT01,GT07] [--workers 4]

Each case in scripts/ground_truth_cases.json is a fictional company whose evidence is injected into the
evidence cache, so no web search runs and the ICP is fixed (no inference call). Only the verdict call is
paid (about $0.03 each). Reports per run:
  decision      strict: equals the expected decision; acceptable: inside the case's acceptable set
  criteria      share of specified ICP criteria whose status is one the case accepts
  spurious      criteria marked not_met that the ICP never specified
  coverage      failed sources, evidence gaps and confidence ceiling equal the expected values exactly
  citations     met / not_met criteria that cite at least one source
"""

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = REPO_ROOT / "scripts" / "ground_truth_cases.json"
sys.path.insert(0, str(REPO_ROOT))

from backend.agent import evidence_cache  # noqa: E402
from backend.agent.criteria import criterion_key, specified_keys  # noqa: E402

TECH_CATEGORIES = ("frontend", "backend", "infrastructure", "analytics", "crm_sales", "other")



def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def build_icp(spec: dict, case: dict) -> dict:
    return dict(spec["icps"][case["icp"]])


def build_evidence(case: dict) -> dict:
    """Expand a case into the evidence dict the three research tools would have returned."""
    slug = case["website"].split(".")[0]
    tech_case, hiring_case = case["technology"], case["hiring"]

    if "error" in tech_case:
        tech = {"company_name": case["company"], "technologies": {}, "search_text": "", "source_urls": [], "error": tech_case["error"]}
    else:
        technologies = {category: list(tech_case.get(category, [])) for category in TECH_CATEGORIES}
        tools = [tool for group in technologies.values() for tool in group]
        text = case.get("technology_text") or f"{case['company']} engineering and finance job posts mention {', '.join(tools)}."
        tech = {
            "company_name": case["company"], "technologies": technologies, "search_text": text,
            "source_urls": [f"https://stackshare.io/{slug}", f"https://{case['website']}/blog/engineering"],
        }

    if "error" in hiring_case:
        hiring = {"company_name": case["company"], "open_positions": [], "hiring_departments": [], "search_text": "",
                  "source_urls": [], "error": hiring_case["error"]}
    else:
        roles = hiring_case.get("open_positions", [])
        text = case.get("hiring_text") or f"{case['company']} careers page lists: {', '.join(roles)}."
        hiring = {
            "company_name": case["company"], "open_positions": list(roles),
            "hiring_departments": hiring_case.get("hiring_departments", []),
            "hiring_active": hiring_case.get("hiring_active", bool(roles)),
            "headcount_signal": hiring_case.get("headcount_signal", "unknown"),
            "search_text": text, "source_urls": [f"https://{case['website']}/careers"],
        }

    web = {"fundamentals": "", "news": "", "source_urls": [], "fundamentals_error": None, "news_error": None}
    if case.get("web_error"):
        web.update(error=case["web_error"], fundamentals_error="Request timed out", news_error="Request timed out")
    else:
        signals = {"total_funding": "Unknown", "headcount": None, "founded_year": None, "headquarters": None, **case["signals"]}
        web.update(fundamentals=case["fundamentals"], company_signals=signals)
        web["source_urls"].append(f"https://www.crunchbase.com/organization/{slug}")
        if case.get("news_error"):
            web["news_error"] = case["news_error"]
        else:
            web["news"] = case["news"]
            web["source_urls"].append(f"https://techcrunch.com/2026/{slug}")

    return {
        "technology": {"raw_data": tech, "summary": ""},
        "hiring": {"raw_data": hiring, "summary": ""},
        "web_search": {"raw_data": web, "summary": ""},
    }


def score_verdict(case: dict, icp: dict, verdict: dict) -> dict:
    """Compare one pipeline verdict with the case's ground truth."""
    acceptable = case.get("acceptable", [case["expected"]])
    statuses = {}
    for item in verdict.get("criteria", []):
        key = criterion_key(item.get("criterion", ""))
        if key and key not in statuses:
            statuses[key] = item

    criteria_misses = []
    for key, allowed in case["criteria"].items():
        got = statuses.get(key, {}).get("status", "missing")
        if got not in allowed:
            criteria_misses.append(f"{key}: {got} (want {'/'.join(allowed)})")

    unspecified = set(statuses) - set(specified_keys(icp))
    spurious = [key for key in unspecified if statuses[key].get("status") == "not_met"]

    graded = [item for item in verdict.get("criteria", []) if item.get("status") in ("met", "not_met")]
    coverage = verdict["coverage"]
    expected_coverage = case["coverage"]
    return {
        "decision": verdict["decision"],
        "strict": verdict["decision"] == case["expected"],
        "acceptable": verdict["decision"] in acceptable,
        "criteria_correct": len(case["criteria"]) - len(criteria_misses),
        "criteria_total": len(case["criteria"]),
        "criteria_misses": criteria_misses,
        "spurious_not_met": spurious,
        "coverage_exact": (
            coverage["failed_sources"] == expected_coverage["failed_sources"]
            and coverage["evidence_gaps"] == expected_coverage["evidence_gaps"]
            and coverage["ceiling"] == expected_coverage["ceiling"]
        ),
        "confidence": verdict["confidence"],
        "model_confidence": verdict["model_confidence"],
        "cited": sum(1 for item in graded if item.get("source_ids")),
        "cited_total": len(graded),
        "reasoning": verdict.get("reasoning", ""),
        "criteria": [{k: c.get(k) for k in ("criterion", "status", "source_ids")} for c in verdict.get("criteria", [])],
    }


def run_case(spec: dict, case: dict, runs: int) -> dict:
    from backend.agent.pipeline import run_evaluation_pipeline

    icp = build_icp(spec, case)
    key = evidence_cache.cache_key(case["company"], case["website"])
    results = []
    for _ in range(runs):
        evidence_cache.put(key, build_evidence(case))
        result = run_evaluation_pipeline(case["company"], icp, case["website"], use_cache=True)
        results.append(score_verdict(case, icp, result["verdict"]))
    decisions = [r["decision"] for r in results]
    return {
        "id": case["id"], "company": case["company"], "tests": case["tests"],
        "expected": case["expected"], "acceptable": case.get("acceptable", [case["expected"]]),
        "boundary": case.get("boundary", False),
        "decisions": decisions, "stable": len(set(decisions)) == 1, "runs": results,
    }


def summarize(rows: list[dict]) -> dict:
    runs = [run for row in rows for run in row["runs"]]
    strict_rows = [row for row in rows if not row["boundary"]]
    strict_runs = [run for row in strict_rows for run in row["runs"]]

    def share(items, test):
        return round(sum(1 for item in items if test(item)) / len(items), 3) if items else None

    return {
        "cases": len(rows),
        "runs": len(runs),
        "decision_acceptable": share(runs, lambda r: r["acceptable"]),
        "decision_strict_all": share(runs, lambda r: r["strict"]),
        "decision_strict_non_boundary": share(strict_runs, lambda r: r["strict"]),
        "criteria_accuracy": round(sum(r["criteria_correct"] for r in runs) / sum(r["criteria_total"] for r in runs), 3),
        "runs_with_spurious_not_met": sum(1 for r in runs if r["spurious_not_met"]),
        "coverage_exact": share(runs, lambda r: r["coverage_exact"]),
        "stability": share(rows, lambda row: row["stable"]),
        "citation_coverage": round(sum(r["cited"] for r in runs) / max(1, sum(r["cited_total"] for r in runs)), 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default=str(REPO_ROOT / "scripts" / "ground_truth_results.json"))
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from eval_verdicts import UsageCapture

    spec = load_cases()
    wanted = {i.strip() for i in args.only.split(",") if i.strip()}
    cases = [case for case in spec["cases"] if not wanted or case["id"] in wanted]

    capture = UsageCapture()
    logging.getLogger().addHandler(capture)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Keep stdout to the result table; telemetry still reaches the capture handler.
    for handler in logging.getLogger().handlers:
        if handler is not capture:
            handler.setLevel(logging.WARNING)

    evidence_cache.clear()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(lambda case: run_case(spec, case, args.runs), cases))

    for row in rows:
        first = row["runs"][0]
        mark = "ok  " if all(r["acceptable"] for r in row["runs"]) else "MISS"
        misses = "; ".join(sorted({m for r in row["runs"] for m in r["criteria_misses"]}))
        print(f"{row['id']} {row['company']:<22} want {'/'.join(row['acceptable']):<22} got {'/'.join(row['decisions']):<38} "
              f"{mark} conf {first['confidence']}{'' if first['coverage_exact'] else ' COVERAGE MISMATCH'}"
              f"{'  criteria: ' + misses if misses else ''}")

    summary = summarize(rows)
    summary["cost_usd_total"] = round(capture.cost(), 3)
    summary["llm_calls"] = len(capture.calls)
    Path(args.output).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
