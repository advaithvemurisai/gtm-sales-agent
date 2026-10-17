"""Evaluate the research step (live web search + extraction) against verified facts about real companies.

Run from the repo root: python scripts/eval_web_search.py [--runs 1] [--only WS01,WS16] [--workers 4]

Each case in scripts/web_search_cases.json lists the acceptable values for the fields the verdict relies on.
Makes paid API calls with web search (about 7 calls per company per run). Reports per field accuracy,
source failures, hallucinations on a fictional company, latency and cost.
"""

import argparse
import json
import logging
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = REPO_ROOT / "scripts" / "web_search_cases.json"
sys.path.insert(0, str(REPO_ROOT))

FIELDS = ("funding_stage", "headcount_range", "founded_year", "headquarters", "technology", "hiring")
_EMPTY = (None, "", "Unknown", "unknown", "null")
_GOT_KEY = {"technology": "technologies", "hiring": "open_positions"}


def _matches_word(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<![\w.+]){re.escape(needle.lower())}(?![\w+])", haystack.lower()) is not None


def grade(case: dict, evidence: dict) -> dict:
    """Grade one research result. A field is None when the case doesn't grade it."""
    tech = evidence["technology"]["raw_data"]
    hiring = evidence["hiring"]["raw_data"]
    web = evidence["web_search"]["raw_data"]
    signals = web.get("company_signals") or {}
    tools = [tool for group in (tech.get("technologies") or {}).values() for tool in group]

    results: dict = {}
    for field in ("funding_stage", "headcount_range"):
        results[field] = signals.get(field, "Unknown") in case[field]
    results["founded_year"] = signals.get("founded_year") in case["founded_year"]

    hq = signals.get("headquarters")
    if case["headquarters"] is None:
        results["headquarters"] = None
    elif case["headquarters"] == [None]:
        results["headquarters"] = hq in _EMPTY
    else:
        results["headquarters"] = bool(hq) and any(city.lower() in hq.lower() for city in case["headquarters"])

    if tech.get("error"):
        results["technology"] = False
    elif case["tech_any"]:
        results["technology"] = any(_matches_word(want, tool) for want in case["tech_any"] for tool in tools)
    else:
        results["technology"] = not tools

    if hiring.get("error"):
        results["hiring"] = False
    elif case["hiring_active"] is None:
        results["hiring"] = None
    elif case["hiring_active"]:
        results["hiring"] = bool(hiring.get("hiring_active")) and bool(hiring.get("open_positions"))
    else:
        results["hiring"] = not hiring.get("open_positions")

    errors = {name: err for name, err in (
        ("technology", tech.get("error")), ("hiring", hiring.get("error")),
        ("fundamentals", web.get("fundamentals_error")), ("news", web.get("news_error")),
    ) if err}
    return {
        "fields": results,
        "got": {
            "funding_stage": signals.get("funding_stage"), "headcount_range": signals.get("headcount_range"),
            "founded_year": signals.get("founded_year"), "headquarters": hq,
            "technologies": tools[:12], "open_positions": (hiring.get("open_positions") or [])[:5],
        },
        "errors": errors,
        "source_count": len({*tech.get("source_urls", []), *hiring.get("source_urls", []), *web.get("source_urls", [])}),
    }


def run_case(case: dict, runs: int) -> dict:
    from backend.agent.pipeline import _gather_evidence
    from backend.errors import is_billing_error

    graded = []
    for _ in range(runs):
        started = time.perf_counter()
        evidence = _gather_evidence(case["company"], case["website"])
        result = grade(case, evidence)
        # The tools record failures as strings; a billing failure is not a search miss, so stop.
        if any(is_billing_error(Exception(err)) for err in result["errors"].values()):
            raise RuntimeError(f"billing error on {case['id']}: {next(iter(result['errors'].values()))[:160]}")
        result["latency_s"] = round(time.perf_counter() - started, 1)
        graded.append(result)
    return {"id": case["id"], "company": case["company"], "nonexistent": case.get("nonexistent", False), "runs": graded}


def summarize(rows: list[dict]) -> dict:
    runs = [run for row in rows for run in row["runs"]]
    per_field = {}
    for field in FIELDS:
        scored = [run["fields"][field] for run in runs if run["fields"][field] is not None]
        per_field[field] = round(sum(scored) / len(scored), 3) if scored else None
    graded = [ok for run in runs for ok in run["fields"].values() if ok is not None]
    latencies = [run["latency_s"] for run in runs]
    stable = [
        row for row in rows
        if len({json.dumps(run["got"]["funding_stage"]) + str(run["got"]["headcount_range"]) for run in row["runs"]}) == 1
    ]
    return {
        "companies": len(rows),
        "runs": len(runs),
        "field_accuracy": round(sum(graded) / len(graded), 3),
        "per_field": per_field,
        "runs_with_source_errors": sum(1 for run in runs if run["errors"]),
        "firmographics_stable": f"{len(stable)}/{len(rows)}" if runs and len(runs) > len(rows) else None,
        "latency_p50_s": round(statistics.median(latencies), 1),
        "latency_max_s": max(latencies),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default=str(REPO_ROOT / "scripts" / "web_search_results.json"))
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from eval_verdicts import UsageCapture

    spec = json.loads(CASES_PATH.read_text())
    wanted = {i.strip() for i in args.only.split(",") if i.strip()}
    cases = [case for case in spec["cases"] if not wanted or case["id"] in wanted]

    capture = UsageCapture()
    root = logging.getLogger()
    root.addHandler(capture)
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for handler in root.handlers:
        if handler is not capture:
            handler.setLevel(logging.ERROR)

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_case, case, args.runs) for case in cases]
        for future in futures:
            try:
                rows.append(future.result())
            except Exception as error:  # e.g. billing: keep what finished and report it
                print(f"Skipped a case: {error}", file=sys.stderr)
    if not rows:
        raise SystemExit("No cases completed.")

    for row in rows:
        for run in row["runs"]:
            misses = [f"{field}={run['got'][_GOT_KEY.get(field, field)]}" for field, ok in run["fields"].items() if ok is False]
            scored = [ok for ok in run["fields"].values() if ok is not None]
            print(f"{row['id']} {row['company']:<22} {sum(scored)}/{len(scored)} fields  {run['latency_s']:>5}s"
                  f"{'  errors: ' + ', '.join(run['errors']) if run['errors'] else ''}"
                  f"{'  misses: ' + '; '.join(misses) if misses else ''}")

    summary = summarize(rows)
    summary["cost_usd_total"] = round(capture.cost(), 3)
    summary["llm_calls"] = len(capture.calls)
    Path(args.output).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
