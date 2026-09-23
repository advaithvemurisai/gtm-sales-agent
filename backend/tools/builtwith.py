import os
import json
import time
from datetime import date
from anthropic import Anthropic
from typing import Dict, Any
import logging
from backend.telemetry import log_anthropic_usage
from backend.config import HAIKU_MODEL, SONNET_MODEL

logger = logging.getLogger(__name__)


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
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    log_anthropic_usage(
        logger,
        operation="builtwith.extract_tech_stack",
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
            "frontend": [],
            "backend": [],
            "infrastructure": [],
            "analytics": [],
            "crm_sales": [],
            "other": []
        }


def get_builtwith_data(company_name: str) -> Dict[str, Any]:
    """
    Finds tech stack signals for a company via web search.
    Searches job postings, engineering blogs, and BuiltWith/Stackshare profiles.
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    builtwith_data = {
        "company_name": company_name,
        "technologies": {},
        "source_urls": [],
        "error": None
    }

    try:
        query = (
            f'"{company_name}" tech stack technologies '
            f'site:stackshare.io OR site:builtwith.com OR "built with" OR "powered by" '
            f'OR engineering blog {date.today().year - 1} {date.today().year}'
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
            operation="builtwith.web_search",
            model=model,
            started_at=started_at,
            response=response,
        )

        text_blocks = [block for block in response.content if getattr(block, "type", None) == "text"]
        cited_blocks = [block for block in text_blocks if getattr(block, "citations", None) or []]
        text = " ".join(block.text for block in (cited_blocks or text_blocks))
        builtwith_data["source_urls"] = list(dict.fromkeys(citation.url for block in text_blocks for citation in (getattr(block, "citations", None) or []) if getattr(citation, "url", None)))

        builtwith_data["technologies"] = _extract_tech_stack(company_name, text, client)

    except Exception as e:
        builtwith_data["error"] = str(e)
        logger.warning(f"BuiltWith web search failed for {company_name}: {e}")

    return {
        "raw_data": builtwith_data,
        "summary": None
    }
