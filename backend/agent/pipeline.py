import logging
import os
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic
from backend.telemetry import log_anthropic_usage, timed_operation
from backend.tools.builtwith import get_builtwith_data
from backend.tools.careers_scraper import get_careers_page_data
from backend.tools.web_search import get_web_search_data
from backend.config import SONNET_MODEL

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
    Run the evaluation pipeline with independent evidence sources in parallel.

    Args:
        company_name: The company name
        icp_profile: Structured ICP dict from Phase 1 (or stub defaults)

    Returns:
        Dict with summaries and final verdict
    """
    logger.info("Starting evaluation pipeline for company=%s", company_name)
    system_prompt = load_prompt("evaluation_system_prompt.txt")

    with ThreadPoolExecutor(max_workers=3) as executor:
        builtwith_future = executor.submit(get_builtwith_data, company_name)
        careers_future = executor.submit(get_careers_page_data, company_name)
        web_search_future = executor.submit(get_web_search_data, company_name)
        builtwith_result = builtwith_future.result()
        careers_result = careers_future.result()
        web_search_result = web_search_future.result()

    with ThreadPoolExecutor(max_workers=4) as executor:
        builtwith_summary_future = executor.submit(_summarize_tool_result, builtwith_result, "Technology Signals", system_prompt)
        careers_summary_future = executor.submit(_summarize_tool_result, careers_result, "Hiring Signals", system_prompt)
        fundamentals_summary_future = executor.submit(
            _summarize_tool_result,
            {"raw_data": web_search_result["raw_data"]["fundamentals"], "error": web_search_result["raw_data"].get("error")},
            "Company Fundamentals",
            system_prompt,
        )
        news_summary_future = executor.submit(
            _summarize_tool_result,
            {"raw_data": web_search_result["raw_data"]["news"], "error": web_search_result["raw_data"].get("error")},
            "Recent News",
            system_prompt,
        )
        builtwith_summary = builtwith_summary_future.result()
        careers_summary = careers_summary_future.result()
        fundamentals_summary = fundamentals_summary_future.result()
        news_summary = news_summary_future.result()
    builtwith_result["summary"] = builtwith_summary
    careers_result["summary"] = careers_summary
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
    raw_data = result.get("raw_data")
    error = result.get("error") or (raw_data.get("error") if isinstance(raw_data, dict) else None)
    if error:
        logger.warning("Skipping summary for failed %s source: %s", tool_name, error)
        return f"SOURCE FAILED: {tool_name}. No evidence was available from this source."
    prompt = f"Summarize this {tool_name} data in 2-3 sentences focusing on signals relevant to sales fit:\n\n{json.dumps(raw_data, indent=2)}"

    model = SONNET_MODEL
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

    model = SONNET_MODEL
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
        "decision": None,
        "reasoning": "",
        "signals": []
    }

    lines = [line.strip() for line in verdict_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        normalized_line = re.sub(
            r"^[*_`]*(VERDICT|DECISION|REASONING|WHY|KEY SIGNALS|SIGNALS|KEY TAKEAWAYS|CONFIDENCE)[*_`]*\s*:[*_`]*",
            lambda match: f"{match.group(1)}:",
            line,
            flags=re.I,
        ).strip()
        if re.match(r"^(VERDICT|DECISION)\s*:", normalized_line, re.I):
            decision_text = normalized_line.split(":", 1)[1].strip()
            for option in ["PURSUE", "DEPRIORITIZE", "WATCH"]:
                if option in decision_text.upper():
                    verdict["decision"] = option
                    break

        elif re.match(r"^(REASONING|WHY)\s*:", normalized_line, re.I):
            reasoning = normalized_line.split(":", 1)[1].strip()
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                next_normalized_line = re.sub(r"^[*_`]*(KEY SIGNALS|SIGNALS|KEY TAKEAWAYS|CONFIDENCE)[*_`]*\s*:[*_`]*", r"\1:", next_line, flags=re.I)
                if re.match(r"^(KEY SIGNALS|SIGNALS|KEY TAKEAWAYS|CONFIDENCE)\s*:", next_normalized_line, re.I):
                    break
                if next_line:
                    reasoning += " " + next_line
                j += 1
            verdict["reasoning"] = re.sub(r"\s+", " ", reasoning).strip()

        elif re.match(r"^(KEY SIGNALS|SIGNALS|KEY TAKEAWAYS)\s*:", normalized_line, re.I):
            for j in range(i + 1, len(lines)):
                signal_line = lines[j].strip()
                if re.match(r"^[-•*]\s+", signal_line):
                    signal = signal_line[2:].strip()
                    if signal:
                        verdict["signals"].append(re.sub(r"\*\*([^*]+)\*\*", r"\1", signal))
                elif signal_line and not signal_line.startswith("-"):
                    break

        elif re.match(r"^CONFIDENCE\s*:", normalized_line, re.I):
            confidence = normalized_line.split(":", 1)[1].strip().lower().split()[0]
            if confidence in {"low", "medium", "high"}:
                verdict["confidence"] = confidence

    if not verdict["decision"] or not verdict["reasoning"]:
        raise ValueError("Verdict response was missing a decision or reasoning section")

    verdict["reasoning"] = re.sub(r"\s+", " ", verdict["reasoning"]).strip()
    verdict["signals"] = [re.sub(r"\s+", " ", signal).strip() for signal in verdict["signals"] if re.sub(r"\s+", " ", signal).strip()]

    return verdict
