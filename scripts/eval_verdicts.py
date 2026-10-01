"""Evaluate verdict quality on labeled cases.

Run from the repo root: python scripts/eval_verdicts.py [--runs 3] [--limit N] [--fresh-stability]

Requires ANTHROPIC_API_KEY (environment or .env) and makes paid API calls. Reports:
  agreement          share of first-run verdicts inside the case's expected decision set
  stability          share of cases whose decision is identical across all runs. By default the
                     repeat runs reuse the cached evidence, so this isolates verdict variance;
                     --fresh-stability re-researches every run to include search variance too
  citation coverage  share of signals and criteria that cite at least one real source
  latency            p50 / p95 of a fresh (uncached) run
  cost               token cost per fresh run from the telemetry logs (web search fees excluded)
"""

import argparse
import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from backend.agent.icp import infer_icp_signals  # noqa: E402
from backend.agent.pipeline import run_evaluation_pipeline  # noqa: E402

# USD per 1M tokens (input, output), from Anthropic's published first-party rates. Update if they change.
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-4-5": (1.00, 5.00)}
_USAGE = re.compile(r"LLM call completed operation=(\S+) model=(\S+) .*?input_tokens=(\d+) output_tokens=(\d+)")


class UsageCapture(logging.Handler):
    """Collects the telemetry line each LLM call logs, so cost needs no extra instrumentation."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.calls: list[tuple[str, str, int, int]] = []

    def emit(self, record):
        match = _USAGE.search(record.getMessage())
        if match:
            op, model, tokens_in, tokens_out = match.groups()
            self.calls.append((op, model, int(tokens_in), int(tokens_out)))

    def reset(self):
        self.calls = []

    def cost(self) -> float:
        total = 0.0
        for _, model, tokens_in, tokens_out in self.calls:
            price_in, price_out = PRICES.get(model, (0.0, 0.0))
            total += (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        return total


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct * (len(ordered) - 1)))]


def citation_coverage(verdict: dict) -> tuple[int, int]:
    items = [*verdict.get("signals", []), *verdict.get("criteria", [])]
    return sum(1 for item in items if item.get("source_ids")), len(items)


def run_case(case, icp, args, capture, decisions, row):
    for run in range(args.runs):
        capture.reset()
        started = time.perf_counter()
        result = run_evaluation_pipeline(
            case["company"], icp, case["website"], use_cache=(run > 0 and not args.fresh_stability)
        )
        elapsed = time.perf_counter() - started
        verdict = result["verdict"]
        decisions.append(verdict["decision"])
        if run == 0:
            cited, total = citation_coverage(verdict)
            row.update(
                decision=verdict["decision"], confidence=verdict["confidence"],
                model_confidence=verdict["model_confidence"], latency_s=round(elapsed, 1),
                cost_usd=round(capture.cost(), 4), llm_calls=len(capture.calls),
                cited=cited, cited_total=total,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="only the first N cases")
    parser.add_argument("--fresh-stability", action="store_true")
    parser.add_argument("--output", default=str(REPO_ROOT / "scripts" / "eval_results.json"))
    args = parser.parse_args()

    spec = json.loads((REPO_ROOT / "scripts" / "eval_cases.json").read_text())
    cases = spec["cases"][: args.limit]
    capture = UsageCapture()
    logging.getLogger().addHandler(capture)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    icps = {}
    for key in {case["product"] for case in cases}:
        icp = infer_icp_signals(spec["products"][key])
        icp["raw_description"] = spec["products"][key]
        icps[key] = icp

    rows = []
    for case in cases:
        icp = icps[case["product"]]
        decisions, row = [], {**case}
        try:
            run_case(case, icp, args, capture, decisions, row)
        except Exception as error:  # e.g. billing or rate limits: keep what finished and report it
            print(f"Stopping after {len(rows)} of {len(cases)} cases: {error}", file=sys.stderr)
            break
        row["decisions"] = decisions
        row["agree"] = decisions[0] in case["expected"]
        row["stable"] = len(set(decisions)) == 1
        rows.append(row)
        print(f"{case['company']:<10} {case['product']:<10} {'/'.join(decisions):<40} "
              f"{'ok ' if row['agree'] else 'MISS'} {row['latency_s']}s ${row['cost_usd']}", flush=True)

    if not rows:
        raise SystemExit("No cases completed.")
    n = len(rows)
    cited = sum(r["cited"] for r in rows)
    cited_total = sum(r["cited_total"] for r in rows)
    latencies = [r["latency_s"] for r in rows]
    summary = {
        "cases": n,
        "runs_per_case": args.runs,
        "agreement": round(sum(r["agree"] for r in rows) / n, 3),
        "stability": round(sum(r["stable"] for r in rows) / n, 3),
        "citation_coverage": round(cited / cited_total, 3) if cited_total else 0,
        "latency_p50_s": round(statistics.median(latencies), 1),
        "latency_p95_s": round(percentile(latencies, 0.95), 1),
        "cost_per_run_usd": round(statistics.mean(r["cost_usd"] for r in rows), 3),
        "llm_calls_per_run": round(statistics.mean(r["llm_calls"] for r in rows), 1),
        "confidence_capped": sum(r["confidence"] != r["model_confidence"] for r in rows),
    }
    Path(args.output).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
