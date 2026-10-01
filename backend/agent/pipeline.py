import logging
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from backend.telemetry import timed_operation
from backend.tools.tech_signals import get_tech_signals
from backend.tools.hiring_signals import get_hiring_signals
from backend.tools.web_search import get_web_search_data
from backend.agent import evidence_cache
from backend.agent.confidence import assess_coverage, cap_confidence
from backend.config import MAX_EVIDENCE_CHARS, SONNET_MODEL
from backend.llm import generate_json, get_client, load_prompt

logger = logging.getLogger("gtm_agent.pipeline")

_SOURCE_IDS = {"type": "array", "items": {"type": "integer"}}
_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["PURSUE", "WATCH", "DEPRIORITIZE"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "reasoning": {"type": "string"},
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "source_ids": _SOURCE_IDS},
                "required": ["text", "source_ids"],
                "additionalProperties": False,
            },
        },
        "next_step": {"type": "string"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "status": {"type": "string", "enum": ["met", "not_met", "unknown"]},
                    "evidence": {"type": "string"},
                    "source_ids": _SOURCE_IDS,
                },
                "required": ["criterion", "status", "evidence", "source_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decision", "confidence", "reasoning", "signals", "next_step", "criteria"],
    "additionalProperties": False,
}



def _gather_evidence(company_name: str, company_website: str | None) -> dict:
    """Run the three independent evidence sources in parallel."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        technology = executor.submit(get_tech_signals, company_name, company_website)
        hiring = executor.submit(get_hiring_signals, company_name, company_website)
        web_search = executor.submit(get_web_search_data, company_name, company_website)
        return {
            "technology": technology.result(),
            "hiring": hiring.result(),
            "web_search": web_search.result(),
        }


def _has_failure(evidence: dict) -> bool:
    return any(
        evidence[source]["raw_data"].get(key)
        for source, keys in (
            ("technology", ("error",)),
            ("hiring", ("error",)),
            ("web_search", ("error", "fundamentals_error", "news_error")),
        )
        for key in keys
    )


def run_evaluation_pipeline(
    company_name: str,
    icp_profile: dict = None,
    company_website: str | None = None,
    use_cache: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """
    Gather evidence (cached per company), then generate one structured, cited verdict.

    Args:
        company_name: The company name
        icp_profile: Structured ICP dict inferred from what the seller sells
        use_cache: Reuse evidence gathered for this company in the last few hours
        on_progress: Called with "research" then "verdict" as each stage starts

    Returns:
        Dict with the three evidence sources, the numbered sources, and the final verdict
    """
    logger.info("Starting evaluation pipeline for company=%s", company_name)
    system_prompt = load_prompt("evaluation_system_prompt.txt")
    icp_profile = icp_profile or {}

    progress = on_progress or (lambda stage: None)
    key = evidence_cache.cache_key(company_name, company_website)
    evidence = evidence_cache.get(key) if use_cache else None
    if evidence:
        logger.info("Evidence cache hit for company=%s", company_name)
    else:
        progress("research")
        evidence = _gather_evidence(company_name, company_website)
        # Failed sources aren't cached, so a rerun retries them.
        if not _has_failure(evidence):
            evidence_cache.put(key, evidence)

    technology_result = evidence["technology"]
    hiring_result = evidence["hiring"]
    web_search_result = evidence["web_search"]
    web_search_raw = web_search_result["raw_data"]
    sources = _number_sources(technology_result, hiring_result, web_search_result)

    progress("verdict")
    with timed_operation(logger, "generate_verdict", company=company_name):
        verdict = _generate_verdict(icp_profile, evidence, sources, system_prompt)
    _validate_source_ids(verdict, len(sources))

    coverage = assess_coverage(
        icp_profile, technology_result["raw_data"], hiring_result["raw_data"], web_search_raw
    )
    verdict["model_confidence"] = verdict["confidence"]
    verdict["confidence"], verdict["confidence_note"] = cap_confidence(verdict["confidence"], coverage)
    verdict["coverage"] = coverage

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
        "sources": sources,
        "verdict": verdict,
    }


def _number_sources(technology: dict, hiring: dict, web_search: dict) -> list[dict]:
    """One numbered list of every cited URL, so the verdict can cite [n] and the UI can link it."""
    groups = (
        ("technology", technology["raw_data"].get("source_urls", [])),
        ("hiring", hiring["raw_data"].get("source_urls", [])),
        ("web search", web_search["raw_data"].get("source_urls", [])),
    )
    sources: list[dict] = []
    seen: set[str] = set()
    for group, urls in groups:
        for url in urls:
            if url not in seen:
                seen.add(url)
                sources.append({"id": len(sources) + 1, "url": url, "group": group})
    return sources


def _validate_source_ids(verdict: dict, source_count: int) -> None:
    """Drop citation ids the model invented."""
    valid = set(range(1, source_count + 1))
    for item in [*verdict.get("signals", []), *verdict.get("criteria", [])]:
        item["source_ids"] = sorted({i for i in item.get("source_ids", []) if i in valid})


def _trim(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= MAX_EVIDENCE_CHARS else text[:MAX_EVIDENCE_CHARS] + " [truncated]"


def _evidence_section(title: str, error: str | None, extract: object, notes: str) -> str:
    if error:
        return f"### {title}\nSOURCE FAILED: no evidence was available from this source."
    return f"### {title}\nExtracted: {json.dumps(extract)}\nSearch notes: {_trim(notes) or 'none'}"


def _format_evidence(evidence: dict, sources: list[dict]) -> str:
    tech = evidence["technology"]["raw_data"]
    hiring = evidence["hiring"]["raw_data"]
    web = evidence["web_search"]["raw_data"]
    hiring_extract = {k: hiring.get(k) for k in ("open_positions", "hiring_departments", "hiring_active", "headcount_signal")}
    sections = [
        _evidence_section("Technology signals", tech.get("error"), tech.get("technologies"), tech.get("search_text")),
        _evidence_section("Hiring signals", hiring.get("error"), hiring_extract, hiring.get("search_text")),
        _evidence_section(
            "Company fundamentals",
            web.get("fundamentals_error") or web.get("error"),
            web.get("company_signals"),
            web.get("fundamentals"),
        ),
        _evidence_section("Recent news", web.get("news_error") or web.get("error"), None, web.get("news")),
    ]
    source_lines = "\n".join(f"[{s['id']}] {s['url']} ({s['group']})" for s in sources) or "(no sources were cited)"
    return "\n\n".join(sections) + "\n\nNUMBERED SOURCES:\n" + source_lines


def _generate_verdict(icp_profile: dict, evidence: dict, sources: list[dict], system_prompt: str) -> dict:
    """Generate the final structured verdict from the extracted evidence and raw search notes."""
    verdict_prompt_template = load_prompt("verdict_prompt.txt")

    funding_stage = icp_profile.get("funding_stage") or []
    tech_signals = icp_profile.get("tech_signals") or []
    hiring_signals = icp_profile.get("hiring_signals") or []
    company_signals = evidence["web_search"]["raw_data"].get("company_signals") or {}

    verdict_prompt = verdict_prompt_template.format(
        target_company_size=icp_profile.get("target_company_size") or "not specified",
        funding_stage=", ".join(funding_stage) or "not specified",
        tech_signals=", ".join(tech_signals) or "none specified",
        hiring_signals=", ".join(hiring_signals) or "none specified",
        budget_indicator=icp_profile.get("budget_indicator") or "not specified",
        raw_description=icp_profile.get("raw_description", "not specified"),
        evidence=_format_evidence(evidence, sources),
        company_signals_funding_stage=company_signals.get("funding_stage", "Unknown"),
        company_signals_headcount_range=company_signals.get("headcount_range", "Unknown"),
        company_signals_founded_year=company_signals.get("founded_year", "Unknown"),
        company_signals_headquarters=company_signals.get("headquarters") or "Unknown",
        company_signals_revenue_estimate=company_signals.get("revenue_estimate", "Unknown"),
    )

    return generate_json(
        get_client(),
        model=SONNET_MODEL,
        prompt=verdict_prompt,
        schema=_VERDICT_SCHEMA,
        operation="generate_verdict",
        logger=logger,
        system=system_prompt,
        max_tokens=4000,
        effort="medium",
    )
