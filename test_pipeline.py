#!/usr/bin/env python3
"""
Test script to run the evaluation pipeline directly without the web frontend.

Usage:
    python test_pipeline.py <company_name> <website> [careers_url]

Example:
    python test_pipeline.py "Stripe" "stripe.com" "https://stripe.com/jobs"
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_pipeline.py <company_name>")
        print("Example: python test_pipeline.py 'Stripe'")
        sys.exit(1)

    company_name = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"GTM Sales Intelligence Agent - Pipeline Test")
    print(f"{'='*60}\n")

    print(f"Company: {company_name}")
    print()

    # Run the pipeline
    result = run_evaluation_pipeline(
        company_name=company_name,
        icp_profile={
            "target_company_size": "50-500",
            "funding_stage": ["Series A", "Series B"],
            "tech_signals": [],
            "hiring_signals": [],
            "budget_indicator": "mid-market",
            "raw_description": "B2B SaaS for fintech companies",
        }
    )

    # Display results
    print(f"\n{'='*60}")
    print("EVALUATION RESULTS")
    print(f"{'='*60}\n")

    print("CRUNCHBASE SUMMARY:")
    print("-" * 60)
    print(result["crunchbase"]["summary"])
    print()

    print("BUILTWITH SUMMARY:")
    print("-" * 60)
    print(result["builtwith"]["summary"])
    print()

    print("CAREERS PAGE SUMMARY:")
    print("-" * 60)
    print(result["careers"]["summary"])
    print()

    print("WEB SEARCH SUMMARY:")
    print("-" * 60)
    print(result["web_search"]["summary"])
    print()

    print(f"{'='*60}")
    print("FINAL VERDICT")
    print(f"{'='*60}\n")

    verdict = result["verdict"]
    print(f"Decision: {verdict['decision'].upper()}")
    print()
    print("Reasoning:")
    print(verdict["reasoning"])
    print()

    if verdict["signals"]:
        print("Key Signals:")
        for signal in verdict["signals"]:
            print(f"  • {signal}")
    print()


if __name__ == "__main__":
    main()
