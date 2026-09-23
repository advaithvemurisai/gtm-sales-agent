import os
import json
import time
from anthropic import Anthropic
from typing import Dict, Any
import logging
from backend.telemetry import log_anthropic_usage
from backend.config import HAIKU_MODEL, SONNET_MODEL

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
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    log_anthropic_usage(
        logger,
        operation="careers.extract_hiring_fields",
        model=model,
        started_at=started_at,
        response=response,
    )

    try:
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return {
            "open_positions": [],
            "hiring_departments": [],
            "hiring_active": False,
            "headcount_signal": "unknown"
        }


def get_careers_page_data(company_name: str, careers_url: str = None) -> Dict[str, Any]:
    """
    Finds hiring signals for a company via web search.
    The careers_url param is accepted for backwards compatibility but ignored —
    direct scraping was replaced after guessed domains failed to resolve.
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    careers_data = {
        "company_name": company_name,
        "open_positions": [],
        "hiring_departments": [],
        "hiring_active": False,
        "headcount_signal": "unknown",
        "source_urls": [],
        "error": None
    }

    try:
        query = (
            f'"{company_name}" jobs hiring "open positions" '
            f'OR "job openings" OR careers site:greenhouse.io OR site:lever.co '
            f'OR site:linkedin.com/jobs 2024 2025'
        )
        model = SONNET_MODEL
        started_at = time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=512,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": query}]
        )
        log_anthropic_usage(
            logger,
            operation="careers.web_search",
            model=model,
            started_at=started_at,
            response=response,
        )

        text = " ".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        careers_data["source_urls"] = list(dict.fromkeys(citation.url for block in response.content for citation in getattr(block, "citations", []) if getattr(citation, "url", None)))

        extracted = _extract_hiring_fields(company_name, text, client)
        careers_data.update(extracted)

    except Exception as e:
        careers_data["error"] = str(e)
        logger.warning(f"Careers web search failed for {company_name}: {e}")

    return {
        "raw_data": careers_data,
        "summary": None
    }
