from backend.agent.verdict import format_verdict_display

EVIDENCE_SOURCES = ("technology", "hiring", "web_search")


def _bullets(pairs) -> str:
    return "\n".join(f"- **{label}:** {value}" for label, value in pairs if value)


def _render_technology(raw: dict) -> str:
    stack = raw.get("technologies") or {}
    return _bullets((name.replace("_", " ").title(), ", ".join(tools)) for name, tools in stack.items() if tools)


def _render_hiring(raw: dict) -> str:
    if not raw.get("open_positions") and not raw.get("hiring_departments"):
        return "No open roles found." if not raw.get("error") else ""
    return _bullets([
        ("Hiring actively", "yes" if raw.get("hiring_active") else "no"),
        ("Open roles", ", ".join(raw.get("open_positions") or [])),
        ("Departments", ", ".join(raw.get("hiring_departments") or [])),
        ("Headcount trend", raw.get("headcount_signal") if raw.get("headcount_signal") != "unknown" else ""),
    ])


def _render_web_search(raw: dict) -> str:
    parts = [f"**{title}**\n{raw[key]}" for title, key in (("Fundamentals", "fundamentals"), ("Recent news", "news")) if raw.get(key)]
    return "\n\n".join(parts)


def build_analysis_response(company_name: str, icp_profile: dict, result: dict) -> dict:
    """Shape a pipeline result into the /analyze response (also used for saved examples)."""
    verdict = format_verdict_display(result["verdict"])
    web = result["web_search"]["raw_data"]

    evidence = {
        "company_signals": web.get("company_signals", {}),
        "technology": _render_technology(result["technology"]["raw_data"]),
        "hiring": _render_hiring(result["hiring"]["raw_data"]),
        "web_search": _render_web_search(web),
        "sources": result.get("sources", []),
        "source_errors": {
            source: result[source]["raw_data"].get("error")
            for source in EVIDENCE_SOURCES
            if result[source]["raw_data"].get("error")
        },
        "partial_errors": {
            key: error
            for key in ("fundamentals_error", "news_error")
            if (error := web.get(key)) and not web.get("error")
        },
        "source_urls": {
            source: result[source]["raw_data"].get("source_urls", [])
            for source in EVIDENCE_SOURCES
        },
    }

    return {
        "company_name": company_name,
        "icp_profile": icp_profile,
        "verdict": verdict,
        "evidence": evidence,
    }
