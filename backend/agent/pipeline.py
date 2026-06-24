import os
import json
from anthropic import Anthropic
from backend.tools.crunchbase import get_crunchbase_data
from backend.tools.builtwith import get_builtwith_data
from backend.tools.careers_scraper import get_careers_page_data
from backend.tools.web_search import get_web_search_data


def _get_client():
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_prompt(prompt_file: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "prompts", prompt_file
    )
    with open(prompt_path, 'r') as f:
        return f.read()


def run_evaluation_pipeline(
    company_name: str,
    icp_profile: dict = None,
) -> dict:
    """
    Run Phase 2 evaluation pipeline with four tools in sequence.

    Args:
        company_name: The company name
        icp_profile: Structured ICP dict from Phase 1 (or stub defaults)

    Returns:
        Dict with summaries and final verdict
    """
    system_prompt = load_prompt("evaluation_system_prompt.txt")

    # Step 1: Crunchbase data
    print("Fetching Crunchbase data...")
    crunchbase_result = get_crunchbase_data(company_name)
    crunchbase_summary = _summarize_tool_result(
        crunchbase_result, "Crunchbase", system_prompt
    )
    crunchbase_result["summary"] = crunchbase_summary

    # Step 2: BuiltWith data - company name used to infer website until real API is wired
    print("Fetching BuiltWith data...")
    builtwith_result = get_builtwith_data(company_name)
    builtwith_summary = _summarize_tool_result(
        builtwith_result, "BuiltWith", system_prompt
    )
    builtwith_result["summary"] = builtwith_summary

    # Step 3: Careers page scraper
    print("Scraping careers page...")
    careers_result = get_careers_page_data(company_name)
    careers_summary = _summarize_tool_result(
        careers_result, "Careers Page", system_prompt
    )
    careers_result["summary"] = careers_summary

    # Step 4: Web search
    print("Running web search...")
    web_search_result = get_web_search_data(company_name)
    web_search_summary = _summarize_tool_result(
        web_search_result, "Web Search", system_prompt
    )
    web_search_result["summary"] = web_search_summary

    # Step 5: Generate verdict
    print("Generating verdict...")
    verdict = _generate_verdict(
        company_name,
        icp_profile or {},
        crunchbase_summary,
        builtwith_summary,
        careers_summary,
        web_search_summary,
        system_prompt
    )

    return {
        "company_name": company_name,
        "icp_profile": icp_profile,
        "crunchbase": crunchbase_result,
        "builtwith": builtwith_result,
        "careers": careers_result,
        "web_search": web_search_result,
        "verdict": verdict,
    }


def _summarize_tool_result(result: dict, tool_name: str, system_prompt: str) -> str:
    """
    Use LLM to summarize a tool result.
    """
    prompt = f"Summarize this {tool_name} data in 2-3 sentences focusing on signals relevant to sales fit:\n\n{json.dumps(result['raw_data'], indent=2)}"

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text


def _generate_verdict(
    company_name: str,
    icp_profile: dict,
    crunchbase_summary: str,
    builtwith_summary: str,
    careers_summary: str,
    web_search_summary: str,
    system_prompt: str
) -> dict:
    """
    Generate final verdict based on all four summaries.
    """
    verdict_prompt_template = load_prompt("verdict_prompt.txt")

    verdict_prompt = verdict_prompt_template.format(
        target_company_size=icp_profile.get("target_company_size", "not specified"),
        funding_stage=", ".join(icp_profile.get("funding_stage", [])) or "not specified",
        tech_signals=", ".join(icp_profile.get("tech_signals", [])) or "none specified",
        hiring_signals=", ".join(icp_profile.get("hiring_signals", [])) or "none specified",
        budget_indicator=icp_profile.get("budget_indicator", "not specified"),
        raw_description=icp_profile.get("raw_description", "not specified"),
        crunchbase_summary=crunchbase_summary,
        builtwith_summary=builtwith_summary,
        careers_summary=careers_summary,
        web_search_summary=web_search_summary,
    )

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system_prompt,
        messages=[
            {"role": "user", "content": verdict_prompt}
        ]
    )

    verdict_text = response.content[0].text
    return _parse_verdict(verdict_text)


def _parse_verdict(verdict_text: str) -> dict:
    """
    Parse the LLM verdict response into structured format.
    """
    verdict = {
        "raw_text": verdict_text,
        "decision": "WATCH",  # Default
        "reasoning": "",
        "signals": []
    }

    lines = verdict_text.split('\n')

    for i, line in enumerate(lines):
        if line.startswith("VERDICT:"):
            decision_text = line.replace("VERDICT:", "").strip()
            for option in ["PURSUE", "DEPRIORITIZE", "WATCH"]:
                if option in decision_text.upper():
                    verdict["decision"] = option
                    break

        elif line.startswith("REASONING:"):
            # Capture reasoning (can span multiple lines)
            reasoning = line.replace("REASONING:", "").strip()
            if i + 1 < len(lines):
                # Continue reading lines until we hit KEY SIGNALS
                j = i + 1
                while j < len(lines) and not lines[j].startswith("KEY SIGNALS"):
                    if lines[j].strip():
                        reasoning += " " + lines[j].strip()
                    j += 1
            verdict["reasoning"] = reasoning

        elif line.startswith("KEY SIGNALS:"):
            # Extract signals
            for j in range(i + 1, len(lines)):
                signal_line = lines[j].strip()
                if signal_line.startswith("- "):
                    signal = signal_line[2:].strip()
                    if signal:
                        verdict["signals"].append(signal)

    return verdict
