import time
import logging
from datetime import date
from typing import Dict, Any

from anthropic import Anthropic

from backend.config import HAIKU_MODEL
from backend.llm import get_client, parse_json_object, response_text, run_web_search
from backend.telemetry import log_anthropic_usage

logger = logging.getLogger(__name__)

_EMPTY_STACK = {
    "frontend": [],
    "backend": [],
    "infrastructure": [],
    "analytics": [],
    "crm_sales": [],
    "other": [],
}


def _extract_tech_stack(company_name: str, text: str, client: Anthropic) -> dict:
    """Use Haiku to extract structured tech stack from web search text."""
    prompt = f"""Extract technology stack information for {company_name} from this text.
Return ONLY valid JSON with exactly these fields, no other text:
{{
    "frontend": ["list of frontend technologies"],
    "backend": ["list of backend/server technologies"],
    "infrastructure": ["list of cloud/infra/devops tools"],
    "analytics": ["list of analytics/data tools"],
    "crm_sales": ["list of CRM or sales tools"],
    "other": ["any other notable tools or platforms"]
}}
Only include technologies explicitly mentioned. Use empty arrays if not found.

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
        operation="tech_signals.extract_tech_stack",
        model=model,
        started_at=started_at,
        response=response,
    )

    try:
        return parse_json_object(response_text(response))
    except Exception:
        logger.warning("Could not parse tech stack JSON for %s", company_name)
        return dict(_EMPTY_STACK)


def get_tech_signals(company_name: str) -> Dict[str, Any]:
    """
    Find technology signals for a company via web search of engineering blogs,
    job posts, and public stack profiles.
    """
    client = get_client()

    tech_data = {
        "company_name": company_name,
        "technologies": {},
        "source_urls": [],
        "error": None
    }

    try:
        year = date.today().year
        query = (
            f"Find which technologies {company_name} uses: languages, frameworks, cloud and data "
            f"infrastructure, analytics, and CRM or sales tools. Check its engineering blog, job "
            f"postings, StackShare, or BuiltWith from {year - 1}-{year}. List the specific tools you find."
        )
        text, tech_data["source_urls"] = run_web_search(client, query, logger, "tech_signals.web_search")
        tech_data["technologies"] = _extract_tech_stack(company_name, text, client)

    except Exception as e:
        tech_data["error"] = str(e)
        logger.exception("Technology signal search failed for %s", company_name)

    return {
        "raw_data": tech_data,
        "summary": None
    }
