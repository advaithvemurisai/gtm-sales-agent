import time
import logging
from datetime import date
from typing import Dict, Any

from anthropic import Anthropic

from backend.config import HAIKU_MODEL
from backend.llm import get_client, parse_json_object, response_text, run_web_search
from backend.telemetry import log_anthropic_usage

logger = logging.getLogger(__name__)


def _extract_hiring_fields(company_name: str, text: str, client: Anthropic) -> dict:
    """Use Haiku to extract structured hiring data from web search text."""
    prompt = f"""Extract hiring information for {company_name} from this text.
Return ONLY valid JSON with exactly these fields, no other text:
{{
    "open_positions": ["list of specific job titles found, max 10"],
    "hiring_departments": ["list of departments e.g. Engineering, Sales, Marketing"],
    "hiring_active": true or false,
    "headcount_signal": "growing|stable|shrinking|unknown"
}}
Only include what is explicitly stated. Use empty arrays if no positions found.

Text:
{text}"""

    model = HAIKU_MODEL
    started_at = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    log_anthropic_usage(
        logger,
        operation="hiring_signals.extract_hiring_fields",
        model=model,
        started_at=started_at,
        response=response,
    )

    try:
        return parse_json_object(response_text(response))
    except Exception:
        logger.warning("Could not parse hiring JSON for %s", company_name)
        return {
            "open_positions": [],
            "hiring_departments": [],
            "hiring_active": False,
            "headcount_signal": "unknown"
        }


def get_hiring_signals(company_name: str, company_website: str | None = None) -> Dict[str, Any]:
    """Find hiring signals for a company via web search of public job listings."""
    client = get_client()

    hiring_data = {
        "company_name": company_name,
        "open_positions": [],
        "hiring_departments": [],
        "hiring_active": False,
        "headcount_signal": "unknown",
        "source_urls": [],
        "error": None
    }

    try:
        year = date.today().year
        identity = f" ({company_website})" if company_website else ""
        query = (
            f"Find the roles {company_name}{identity} is hiring for now, using its careers page or job boards "
            f"such as Greenhouse, Lever, or LinkedIn ({year - 1}-{year}). List specific job titles and "
            f"departments, and say whether headcount looks like it is growing, stable, or shrinking."
        )
        text, hiring_data["source_urls"] = run_web_search(client, query, logger, "hiring_signals.web_search")
        hiring_data.update(_extract_hiring_fields(company_name, text, client))

    except Exception as e:
        hiring_data["error"] = str(e)
        logger.exception("Hiring signal search failed for %s", company_name)

    return {
        "raw_data": hiring_data,
        "summary": None
    }
