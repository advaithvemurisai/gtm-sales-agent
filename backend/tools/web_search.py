import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Dict, Any

from anthropic import Anthropic

from backend.config import HAIKU_MODEL
from backend.llm import get_client, parse_json_object, response_text, run_web_search
from backend.telemetry import log_anthropic_usage


logger = logging.getLogger(__name__)


def parse_company_signals(company_name: str, fundamentals_text: str, client: Anthropic) -> dict:
    """Use Haiku to extract structured fields from fundamentals search result."""
    prompt = f"""Extract company information for {company_name} from this text.
Return ONLY valid JSON with exactly these fields, no other text:
{{
    "funding_stage": "Seed|Series A|Series B|Series C|Growth|Public|Bootstrapped|Unknown",
    "total_funding": "$XM or $XB or Unknown",
    "headcount": integer or null,
    "headcount_range": "1-10|11-50|51-200|201-500|501-1000|1000+ or Unknown",
    "founded_year": integer or null,
    "headquarters": "City, State or null",
    "revenue_estimate": "$XM or Unknown"
}}
Only extract what is explicitly stated. Use null or Unknown if not found.

Text:
{fundamentals_text}"""

    model = HAIKU_MODEL
    started_at = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    log_anthropic_usage(
        logger,
        operation="web_search.parse_company_signals",
        model=model,
        started_at=started_at,
        response=response,
    )

    try:
        return parse_json_object(response_text(response))
    except Exception:
        logger.warning("Could not parse company signals JSON for %s", company_name)
        return {
            "funding_stage": "Unknown",
            "total_funding": "Unknown",
            "headcount": None,
            "headcount_range": "Unknown",
            "founded_year": None,
            "headquarters": None,
            "revenue_estimate": "Unknown"
        }


def get_web_search_data(company_name: str, company_website: str | None = None) -> Dict[str, Any]:
    client = get_client()

    web_search_data = {
        "company_name": company_name,
        "fundamentals": "",
        "news": "",
        "company_signals": {},
        "source_urls": [],
        "error": None
    }

    try:
        identity = f" ({company_website})" if company_website else ""
        fundamentals_query = (
            f"Find {company_name}{identity}'s funding stage, total funding, employee headcount, founding year, "
            f"headquarters, and revenue estimate."
        )
        year = date.today().year
        news_query = (
            f"Find {company_name}{identity}'s most significant news from {year - 1}-{year}: funding, hiring, "
            f"growth, product launches, and partnerships."
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            fundamentals_future = executor.submit(run_web_search, client, fundamentals_query, logger, "web_search.fundamentals")
            news_future = executor.submit(run_web_search, client, news_query, logger, "web_search.news")
            fundamentals_text, fundamentals_urls = fundamentals_future.result()
            news_text, news_urls = news_future.result()
        web_search_data["fundamentals"] = fundamentals_text
        web_search_data["news"] = news_text

        web_search_data["company_signals"] = parse_company_signals(
            company_name, fundamentals_text, client
        )
        web_search_data["source_urls"] = list(dict.fromkeys(fundamentals_urls + news_urls))

    except Exception as e:
        web_search_data["error"] = str(e)
        logger.exception("Web search failed for %s", company_name)

    return {
        "raw_data": web_search_data,
        "summary": None
    }
