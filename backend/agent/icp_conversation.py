import os
import logging
import time
from anthropic import Anthropic
from backend.telemetry import log_anthropic_usage
from backend.config import HAIKU_MODEL, SONNET_MODEL

logger = logging.getLogger("gtm_agent.icp")


def _get_client():
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_prompt(prompt_file: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "prompts", prompt_file
    )
    with open(prompt_path, 'r') as f:
        return f.read()


def run_icp_conversation(company_name: str, product_description: str) -> tuple[str, list]:
    """
    Run Phase 1 ICP conversation with the LLM.

    Args:
        company_name: The target company name
        product_description: Description of what the company sells

    Returns:
        Tuple of (icp_profile_text, conversation_history)
    """
    system_prompt = load_prompt("system_prompt.txt")
    icp_prompt = load_prompt("icp_prompt.txt")

    conversation_history = []
    messages = []

    # Initial message from agent to user
    initial_message = (
        f"Hi! I'm here to evaluate {company_name} as a potential sales target. "
        f"You mentioned they sell: {product_description}\n\n"
        f"To help assess fit, I need to understand your ICP better. "
        f"Can you tell me about your target customer size and industry?"
    )

    conversation_history.append({"role": "assistant", "content": initial_message})

    while True:
        # User provides input
        user_input = input("You: ").strip()
        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})
        messages = [
            {"role": "user" if item["role"] == "user" else "assistant", "content": item["content"]}
            for item in conversation_history
        ]

        # Get LLM response
        model = SONNET_MODEL
        started_at = time.perf_counter()
        response = _get_client().messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt + "\n\n" + icp_prompt,
            messages=messages
        )
        log_anthropic_usage(
            logger,
            operation="icp_conversation_turn",
            model=model,
            started_at=started_at,
            response=response,
        )

        assistant_message = response.content[0].text

        # Check for EVALUATE token
        if _check_evaluate_token(assistant_message):
            # Extract ICP profile from conversation
            icp_profile = _extract_icp_profile(conversation_history)
            return icp_profile, conversation_history

        conversation_history.append({"role": "assistant", "content": assistant_message})
        print(f"\nAssistant: {assistant_message}\n")


def _check_evaluate_token(text: str) -> bool:
    """
    Check if the EVALUATE token appears in the text.
    Case-insensitive, treats it as a standalone line.
    """
    lines = text.strip().split('\n')
    for line in lines:
        if line.strip().upper() == "EVALUATE":
            return True
    return False


def _extract_icp_profile(conversation_history: list) -> str:
    """
    Extract ICP profile from conversation history.
    """
    # Summarize key points from the conversation
    profile_points = []

    for item in conversation_history:
        if item["role"] == "user":
            profile_points.append(item["content"][:100] + "...")

    return "\n".join(profile_points[:5])  # Last 5 user inputs as profile


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
