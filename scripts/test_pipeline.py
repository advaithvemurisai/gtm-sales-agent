#!/usr/bin/env python3
"""Run the evaluation pipeline directly from the command line."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.pipeline import run_evaluation_pipeline


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_pipeline.py <company_name>")
        raise SystemExit(1)

    result = run_evaluation_pipeline(
        company_name=sys.argv[1],
        icp_profile={
            "target_company_size": "50-500",
            "funding_stage": ["Series A", "Series B"],
            "tech_signals": [],
            "hiring_signals": [],
            "budget_indicator": "mid-market",
            "raw_description": "B2B SaaS for fintech companies",
        },
    )
    verdict = result["verdict"]
    print(f"Decision: {verdict['decision']}")
    print(f"Reasoning: {verdict['reasoning']}")
    for signal in verdict["signals"]:
        print(f"- {signal}")


if __name__ == "__main__":
    main()