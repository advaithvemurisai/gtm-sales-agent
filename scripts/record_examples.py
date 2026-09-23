"""Record the three saved landing-page examples using the live analysis pipeline.

Requires ANTHROPIC_API_KEY. This intentionally makes paid API calls; run it only
when you want to refresh the examples.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.agent.icp import infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display

EXAMPLES = [
    ("Vercel", "Spend management and corporate cards for fast-growing tech companies.", "https://vercel.com"),
    ("Notion", "Security compliance automation for scaling SaaS companies.", "https://notion.so"),
    ("Gong", "Data warehouse and analytics platform for revenue operations teams.", "https://gong.io"),
]
OUTPUT_DIR = Path(__file__).parents[1] / "frontend" / "src" / "examples"


def record_example(company_name: str, product_description: str, company_website: str) -> dict:
    profile = infer_icp_signals(product_description)
    profile["raw_description"] = product_description
    result = run_evaluation_pipeline(company_name, profile, company_website)
    verdict = format_verdict_display(result["verdict"])
    evidence = {
        "company_signals": result["web_search"]["raw_data"].get("company_signals", {}),
        "technology": result["technology"]["summary"],
        "hiring": result["hiring"]["summary"],
        "web_search": result["web_search"]["summary"],
        "source_errors": {},
        "source_urls": {source: result[source]["raw_data"].get("source_urls", []) for source in ("technology", "hiring", "web_search")},
    }
    return {
        "company_name": company_name,
        "icp_profile": profile,
        "verdict": verdict,
        "evidence": evidence,
        "summary": {
            "decision": verdict["decision"],
            "signal_count": len(verdict.get("signals", [])),
            "reasoning_preview": verdict.get("reasoning", "")[:220],
            "evidence_sources": ["company_signals", "technology", "hiring", "web_search"],
            "confidence": verdict.get("confidence", "unknown"),
        },
        "product_description": product_description,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for company_name, product_description, company_website in EXAMPLES:
        output = record_example(company_name, product_description, company_website)
        path = OUTPUT_DIR / f"{company_name.lower()}.json"
        path.write_text(json.dumps(output, indent=2) + "\n")
        print(f"Wrote {path}")
