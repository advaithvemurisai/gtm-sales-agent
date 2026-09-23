"""Record the saved landing-page examples using the live analysis pipeline.

Run from the repo root: python scripts/record_examples.py

Requires ANTHROPIC_API_KEY (read from the environment or .env). This makes paid
API calls, so run it only when you want to refresh the examples. The landing page
labels each tab from the verdict it actually got; nothing is edited by hand.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from backend.agent.icp import infer_icp_signals  # noqa: E402
from backend.agent.pipeline import run_evaluation_pipeline  # noqa: E402
from backend.agent.response import build_analysis_response  # noqa: E402

# Mid-size targets alongside a large one, so the saved examples can show more
# than one kind of verdict. Rerun and swap targets if they all land the same way.
EXAMPLES = [
    ("Linear", "Spend management and corporate cards for fast-growing tech companies.", "https://linear.app"),
    ("Attio", "Data warehouse and analytics platform for revenue operations teams.", "https://attio.com"),
    ("Notion", "Security compliance automation for scaling SaaS companies.", "https://notion.so"),
]
OUTPUT_DIR = REPO_ROOT / "frontend" / "src" / "examples"


def record_example(company_name: str, product_description: str, company_website: str) -> dict:
    icp_profile = infer_icp_signals(product_description)
    icp_profile["raw_description"] = product_description
    result = run_evaluation_pipeline(company_name, icp_profile, company_website)
    return {
        **build_analysis_response(company_name, icp_profile, result),
        "product_description": product_description,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for company_name, product_description, company_website in EXAMPLES:
        output = record_example(company_name, product_description, company_website)
        path = OUTPUT_DIR / f"{company_name.lower()}.json"
        path.write_text(json.dumps(output, indent=2) + "\n")
        print(f"Wrote {path.relative_to(REPO_ROOT)}: {output['verdict']['decision']}")
