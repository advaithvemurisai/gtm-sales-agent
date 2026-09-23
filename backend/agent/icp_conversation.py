import os
import logging
import time
from anthropic import Anthropic
from backend.telemetry import log_anthropic_usage
from backend.config import HAIKU_MODEL, SONNET_MODEL

logger = logging.getLogger("gtm_agent.icp")


def _get_client():
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def infer_icp_signals(product_description: str) -> dict:
    """
    Use Haiku to infer all five ICP fields from product description.
    Returns structured dict or safe fallback with nulls.
    """
    import json

    prompt = f"""You are an expert B2B sales strategist. Given a product description, infer the ideal customer profile.

Product: {product_description}

Return ONLY valid JSON with exactly these fields, no other text:
{{
    "target_company_size": "headcount range as string e.g. 50-500, or null if unclear",
    "funding_stage": ["list of likely funding stages e.g. Series A, Series B"],
    "tech_signals": ["3-5 specific tools/platforms the ideal customer likely uses"],
    "hiring_signals": ["3-5 job titles that signal this company is a good fit"],
    "budget_indicator": "startup|mid-market|enterprise"
}}

Rules:
- target_company_size: infer from who typically buys this product. Developer tools → 10-200. Enterprise compliance → 500+. Sales tooling → 50-500.
- funding_stage: infer from budget requirements. Cheap/PLG products → Seed, Series A. Expensive/enterprise → Series B+.
- tech_signals: specific named tools, not categories. "Salesforce" not "CRM". "Segment" not "analytics".
- hiring_signals: specific job titles that signal budget and buying intent. "VP of Engineering" not "engineers".
- budget_indicator: startup = <$10M raised, mid-market = Series A/B, enterprise = Series C+.
- If genuinely unclear on any field, use null for strings or empty list for arrays.
- Never guess wildly. Null is better than wrong."""

    try:
        model = HAIKU_MODEL
        started_at = time.perf_counter()
        response = _get_client().messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        log_anthropic_usage(
            logger,
            operation="infer_icp_signals",
            model=model,
            started_at=started_at,
            response=response,
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        logger.exception("ICP inference failed")
        return {
            "target_company_size": None,
            "funding_stage": [],
            "tech_signals": [],
            "hiring_signals": [],
            "budget_indicator": None
        }
