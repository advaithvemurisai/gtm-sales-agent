import os
import json
import logging
import time
from anthropic import Anthropic
from typing import Dict, Any
from backend.telemetry import log_anthropic_usage


logger = logging.getLogger(__name__)


def _run_search(query: str, client: Anthropic) -> str:
    """Run a single web search and return concatenated text results."""
    model = "claude-sonnet-4-6"
    started_at = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": query}]
    )
    log_anthropic_usage(
        logger,
        operation="web_search.run_search",
        model=model,
        started_at=started_at,
        response=response,
    )
    return " ".join([
        block.text for block in response.content
        if hasattr(block, "text")
    ])


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

    model = "claude-haiku-4-5-20251001"
    started_at = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=256,
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
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return {
            "funding_stage": "Unknown",
            "total_funding": "Unknown",
            "headcount": None,
            "headcount_range": "Unknown",
            "founded_year": None,
            "headquarters": None,
            "revenue_estimate": "Unknown"
        }


def get_web_search_data(company_name: str) -> Dict[str, Any]:
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    web_search_data = {
        "company_name": company_name,
        "fundamentals": "",
        "news": "",
        "company_signals": {},
        "error": None
    }

    try:
        fundamentals_query = (
            f'"{company_name}" company funding stage '
            f'employees headcount founded year revenue headquarters'
        )
        fundamentals_text = _run_search(fundamentals_query, client)
        web_search_data["fundamentals"] = fundamentals_text

        news_query = (
            f'"{company_name}" recent news 2024 2025 '
            f'hiring growth product launch partnerships'
        )
        news_text = _run_search(news_query, client)
        web_search_data["news"] = news_text

        web_search_data["company_signals"] = parse_company_signals(
            company_name, fundamentals_text, client
        )

    except Exception as e:
        web_search_data["error"] = str(e)

    return {
        "raw_data": web_search_data,
        "summary": None
    }
