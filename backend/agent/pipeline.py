import logging
import os
import json
import re
import time
from anthropic import Anthropic
from backend.telemetry import log_anthropic_usage, timed_operation
from backend.tools.builtwith import get_builtwith_data
from backend.tools.careers_scraper import get_careers_page_data
from backend.tools.web_search import get_web_search_data

logger = logging.getLogger("gtm_agent.pipeline")


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
    logger.info("Starting evaluation pipeline for company=%s", company_name)
    system_prompt = load_prompt("evaluation_system_prompt.txt")

    # Step 1: Crunchbase retired - company signals extracted from web search
    crunchbase_result = {
        "raw_data": {"note": "replaced by web search signal extraction"},
        "summary": "Funding and headcount data extracted via web search."
    }

    # Step 2: BuiltWith data
    with timed_operation(logger, "fetch_builtwith", company=company_name):
        builtwith_result = get_builtwith_data(company_name)
    with timed_operation(logger, "summarize_builtwith", company=company_name):
        builtwith_summary = _summarize_tool_result(
            builtwith_result, "BuiltWith", system_prompt
        )
    builtwith_result["summary"] = builtwith_summary

    # Step 3: Careers page scraper
    with timed_operation(logger, "fetch_careers", company=company_name):
        careers_result = get_careers_page_data(company_name)
    with timed_operation(logger, "summarize_careers", company=company_name):
        careers_summary = _summarize_tool_result(
            careers_result, "Careers Page", system_prompt
        )
    careers_result["summary"] = careers_summary

    # Step 4: Web search (two queries: fundamentals + news)
    with timed_operation(logger, "fetch_web_search", company=company_name):
        web_search_result = get_web_search_data(company_name)
    with timed_operation(logger, "summarize_company_fundamentals", company=company_name):
        fundamentals_summary = _summarize_tool_result(
            {"raw_data": web_search_result["raw_data"]["fundamentals"]},
            "Company Fundamentals",
            system_prompt
        )
    with timed_operation(logger, "summarize_recent_news", company=company_name):
        news_summary = _summarize_tool_result(
            {"raw_data": web_search_result["raw_data"]["news"]},
            "Recent News",
            system_prompt
        )
    web_search_result["summary"] = f"{fundamentals_summary}\n\n{news_summary}"
    web_search_summary = web_search_result["summary"]

    # Step 5: Generate verdict
    company_signals = web_search_result["raw_data"].get("company_signals", {})
    with timed_operation(logger, "generate_verdict", company=company_name):
        verdict = _generate_verdict(
            icp_profile or {},
            builtwith_summary,
            careers_summary,
            fundamentals_summary,
            news_summary,
            company_signals,
            system_prompt
        )

    logger.info(
        "Evaluation pipeline completed for %s with decision=%s",
        company_name,
        verdict.get("decision", "WATCH"),
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
    logger.info("Summarizing %s data", tool_name)
    prompt = f"Summarize this {tool_name} data in 2-3 sentences focusing on signals relevant to sales fit:\n\n{json.dumps(result['raw_data'], indent=2)}"

    model = "claude-sonnet-4-6"
    started_at = time.perf_counter()
    response = _get_client().messages.create(
        model=model,
        max_tokens=256,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    log_anthropic_usage(
        logger,
        operation=f"summarize_tool_result.{tool_name}",
        model=model,
        started_at=started_at,
        response=response,
    )

    summary = response.content[0].text
    logger.info("Completed summary for %s", tool_name)
    return summary


def _generate_verdict(
    icp_profile: dict,
    builtwith_summary: str,
    careers_summary: str,
    fundamentals_summary: str,
    news_summary: str,
    company_signals: dict,
    system_prompt: str
) -> dict:
    """
    Generate final verdict based on all summaries and extracted company signals.
    """
    verdict_prompt_template = load_prompt("verdict_prompt.txt")

    funding_stage = icp_profile.get("funding_stage") or []
    tech_signals = icp_profile.get("tech_signals") or []
    hiring_signals = icp_profile.get("hiring_signals") or []

    verdict_prompt = verdict_prompt_template.format(
        target_company_size=icp_profile.get("target_company_size") or "not specified",
        funding_stage=", ".join(funding_stage) or "not specified",
        tech_signals=", ".join(tech_signals) or "none specified",
        hiring_signals=", ".join(hiring_signals) or "none specified",
        budget_indicator=icp_profile.get("budget_indicator") or "not specified",
        raw_description=icp_profile.get("raw_description", "not specified"),
        builtwith_summary=builtwith_summary,
        careers_summary=careers_summary,
        fundamentals_summary=fundamentals_summary,
        news_summary=news_summary,
        company_signals_funding_stage=company_signals.get("funding_stage", "Unknown"),
        company_signals_headcount_range=company_signals.get("headcount_range", "Unknown"),
        company_signals_founded_year=company_signals.get("founded_year", "Unknown"),
        company_signals_headquarters=company_signals.get("headquarters") or "Unknown",
        company_signals_revenue_estimate=company_signals.get("revenue_estimate", "Unknown"),
    )

    model = "claude-sonnet-4-6"
    started_at = time.perf_counter()
    response = _get_client().messages.create(
        model=model,
        max_tokens=512,
        system=system_prompt,
        messages=[
            {"role": "user", "content": verdict_prompt}
        ]
    )
    log_anthropic_usage(
        logger,
        operation="generate_verdict",
        model=model,
        started_at=started_at,
        response=response,
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

    lines = [line.strip() for line in verdict_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        if re.match(r"^(VERDICT|DECISION)\s*:", line, re.I):
            decision_text = line.split(":", 1)[1].strip()
            for option in ["PURSUE", "DEPRIORITIZE", "WATCH"]:
                if option in decision_text.upper():
                    verdict["decision"] = option
                    break

        elif re.match(r"^(REASONING|WHY)\s*:", line, re.I):
            reasoning = line.split(":", 1)[1].strip()
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if re.match(r"^(KEY SIGNALS|SIGNALS|KEY TAKEAWAYS)\s*:", next_line, re.I):
                    break
                if next_line:
                    reasoning += " " + next_line
                j += 1
            verdict["reasoning"] = re.sub(r"\s+", " ", reasoning).strip()

        elif re.match(r"^(KEY SIGNALS|SIGNALS|KEY TAKEAWAYS)\s*:", line, re.I):
            for j in range(i + 1, len(lines)):
                signal_line = lines[j].strip()
                if re.match(r"^[-•*]\s+", signal_line):
                    signal = signal_line[2:].strip()
                    if signal:
                        verdict["signals"].append(signal)
                elif signal_line and not signal_line.startswith("-"):
                    break

    verdict["reasoning"] = re.sub(r"\s+", " ", verdict["reasoning"]).strip()
    verdict["signals"] = [re.sub(r"\s+", " ", signal).strip() for signal in verdict["signals"] if re.sub(r"\s+", " ", signal).strip()]

    return verdict
