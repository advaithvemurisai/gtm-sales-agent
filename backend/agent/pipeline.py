import logging
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from backend.telemetry import log_anthropic_usage, timed_operation
from backend.tools.tech_signals import get_tech_signals
from backend.tools.hiring_signals import get_hiring_signals
from backend.tools.web_search import get_web_search_data
from backend.config import SONNET_MODEL
from backend.llm import get_client, load_prompt, response_text

logger = logging.getLogger("gtm_agent.pipeline")

_SECTION_NAMES = ("VERDICT", "DECISION", "REASONING", "WHY", "KEY SIGNALS", "SIGNALS", "KEY TAKEAWAYS", "CONFIDENCE")
_SECTION_PATTERN = re.compile(
    r"^[*_`#\s]*(" + "|".join(_SECTION_NAMES) + r")[*_`]*\s*:[*_`]*\s*(.*)$",
    re.I,
)
_BULLET_PATTERN = re.compile(r"^[-•*]\s+")


def run_evaluation_pipeline(
    company_name: str,
    icp_profile: dict = None,
) -> dict:
    """
    Run the evaluation pipeline with independent evidence sources in parallel.

    Args:
        company_name: The company name
        icp_profile: Structured ICP dict inferred from what the seller sells

    Returns:
        Dict with summaries and final verdict
    """
    logger.info("Starting evaluation pipeline for company=%s", company_name)
    system_prompt = load_prompt("evaluation_system_prompt.txt")

    with ThreadPoolExecutor(max_workers=3) as executor:
        technology_future = executor.submit(get_tech_signals, company_name)
        hiring_future = executor.submit(get_hiring_signals, company_name)
        web_search_future = executor.submit(get_web_search_data, company_name)
        technology_result = technology_future.result()
        hiring_result = hiring_future.result()
        web_search_result = web_search_future.result()

    web_search_error = web_search_result["raw_data"].get("error")
    with ThreadPoolExecutor(max_workers=4) as executor:
        technology_summary_future = executor.submit(_summarize_tool_result, technology_result, "Technology Signals", system_prompt)
        hiring_summary_future = executor.submit(_summarize_tool_result, hiring_result, "Hiring Signals", system_prompt)
        fundamentals_summary_future = executor.submit(
            _summarize_tool_result,
            {"raw_data": web_search_result["raw_data"]["fundamentals"], "error": web_search_error},
            "Company Fundamentals",
            system_prompt,
        )
        news_summary_future = executor.submit(
            _summarize_tool_result,
            {"raw_data": web_search_result["raw_data"]["news"], "error": web_search_error},
            "Recent News",
            system_prompt,
        )
        technology_summary = technology_summary_future.result()
        hiring_summary = hiring_summary_future.result()
        fundamentals_summary = fundamentals_summary_future.result()
        news_summary = news_summary_future.result()
    technology_result["summary"] = technology_summary
    hiring_result["summary"] = hiring_summary
    web_search_result["summary"] = f"{fundamentals_summary}\n\n{news_summary}"

    company_signals = web_search_result["raw_data"].get("company_signals", {})
    with timed_operation(logger, "generate_verdict", company=company_name):
        verdict = _generate_verdict(
            icp_profile or {},
            technology_summary,
            hiring_summary,
            fundamentals_summary,
            news_summary,
            company_signals,
            system_prompt
        )

    logger.info(
        "Evaluation pipeline completed for %s with decision=%s",
        company_name,
        verdict.get("decision"),
    )

    return {
        "company_name": company_name,
        "icp_profile": icp_profile,
        "technology": technology_result,
        "hiring": hiring_result,
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
    response = get_client().messages.create(
        model=model,
        max_tokens=2000,
        output_config={"effort": "low"},
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

    summary = response_text(response)
    logger.info("Completed summary for %s", tool_name)
    return summary


def _generate_verdict(
    icp_profile: dict,
    technology_summary: str,
    hiring_summary: str,
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
        technology_summary=technology_summary,
        hiring_summary=hiring_summary,
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
    response = get_client().messages.create(
        model=model,
        max_tokens=4000,
        output_config={"effort": "medium"},
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

    return _parse_verdict(response_text(response))


def _section_heading(line: str) -> tuple[str, str] | None:
    """Return (SECTION, rest of line) for a heading like '**Verdict:** PURSUE'."""
    match = _SECTION_PATTERN.match(line)
    if not match:
        return None
    return match.group(1).upper(), match.group(2).strip()


def _parse_verdict(verdict_text: str) -> dict:
    """
    Parse the LLM verdict response into structured format.
    """
    verdict = {
        "raw_text": verdict_text,
        "decision": None,
        "reasoning": "",
        "signals": [],
        "confidence": "unknown",
    }

    lines = [line.strip() for line in verdict_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        heading = _section_heading(line)
        if not heading:
            continue
        section, rest = heading

        if section in ("VERDICT", "DECISION"):
            for option in ["PURSUE", "DEPRIORITIZE", "WATCH"]:
                if option in rest.upper():
                    verdict["decision"] = option
                    break

        elif section in ("REASONING", "WHY"):
            reasoning_lines = [rest]
            for next_line in lines[i + 1:]:
                if _section_heading(next_line):
                    break
                reasoning_lines.append(next_line)
            verdict["reasoning"] = re.sub(r"\s+", " ", " ".join(reasoning_lines)).strip()

        elif section in ("KEY SIGNALS", "SIGNALS", "KEY TAKEAWAYS"):
            for signal_line in lines[i + 1:]:
                if not _BULLET_PATTERN.match(signal_line):
                    break
                signal = _BULLET_PATTERN.sub("", signal_line)
                signal = re.sub(r"\*\*([^*]+)\*\*", r"\1", signal)
                signal = re.sub(r"\s+", " ", signal).strip()
                if signal:
                    verdict["signals"].append(signal)

        elif section == "CONFIDENCE":
            match = re.search(r"\b(low|medium|high)\b", rest, re.I)
            if match:
                verdict["confidence"] = match.group(1).lower()

    if not verdict["decision"] or not verdict["reasoning"]:
        raise ValueError("Verdict response was missing a decision or reasoning section")

    return verdict
