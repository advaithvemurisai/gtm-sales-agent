import os
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


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
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt + "\n\n" + icp_prompt,
            messages=messages
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
    Infer likely tech_signals and hiring_signals from a product description.
    Used by /analyze stub until Phase 1 conversation is wired.
    """
    import json

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system="You extract B2B sales ICP signals from product descriptions. Be specific and concise.",
        messages=[{
            "role": "user",
            "content": (
                f'Given this product description: "{product_description}"\n\n'
                "Return a JSON object with exactly two keys:\n"
                "- tech_signals: list of 2-4 technologies/platforms a likely buyer already uses\n"
                "- hiring_signals: list of 2-4 job titles that indicate a buyer is in-market\n\n"
                "Return only valid JSON, no other text."
            )
        }]
    )

    try:
        signals = json.loads(response.content[0].text)
        return {
            "tech_signals": signals.get("tech_signals", []),
            "hiring_signals": signals.get("hiring_signals", []),
        }
    except (json.JSONDecodeError, KeyError):
        return {"tech_signals": [], "hiring_signals": []}
