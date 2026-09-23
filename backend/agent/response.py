from backend.agent.verdict import format_verdict_display

EVIDENCE_SOURCES = ("technology", "hiring", "web_search")


def build_analysis_response(company_name: str, icp_profile: dict, result: dict) -> dict:
    """Shape a pipeline result into the /analyze response (also used for saved examples)."""
    verdict = format_verdict_display(result["verdict"])

    evidence = {
        "company_signals": result["web_search"]["raw_data"].get("company_signals", {}),
        "technology": result["technology"]["summary"],
        "hiring": result["hiring"]["summary"],
        "web_search": result["web_search"]["summary"],
        "source_errors": {
            source: result[source]["raw_data"].get("error")
            for source in EVIDENCE_SOURCES
            if result[source]["raw_data"].get("error")
        },
        "source_urls": {
            source: result[source]["raw_data"].get("source_urls", [])
            for source in EVIDENCE_SOURCES
        },
    }

    summary = {
        "decision": verdict["decision"],
        "signal_count": len(verdict.get("signals", [])),
        "reasoning_preview": verdict.get("reasoning", "")[:220],
        "evidence_sources": ["company_signals", *EVIDENCE_SOURCES],
        "confidence": verdict.get("confidence", "unknown"),
    }

    return {
        "company_name": company_name,
        "icp_profile": icp_profile,
        "verdict": verdict,
        "evidence": evidence,
        "summary": summary,
    }
