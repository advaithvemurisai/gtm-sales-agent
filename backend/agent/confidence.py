"""Evidence-coverage check that caps the model's self-reported confidence.

The model can claim HIGH confidence on thin evidence, so confidence is bounded by what the code can
verify: how many sources failed and how many ICP criteria have no evidence behind them.
"""

_LEVELS = ("low", "medium", "high")
_UNKNOWN = (None, "", "unknown", "Unknown")


def _failed_sources(technology: dict, hiring: dict, web_search: dict) -> list[str]:
    failed = []
    if technology.get("error"):
        failed.append("technology")
    if hiring.get("error"):
        failed.append("hiring")
    if web_search.get("fundamentals_error") or (web_search.get("error") and not web_search.get("news_error")):
        failed.append("company fundamentals")
    if web_search.get("news_error") or (web_search.get("error") and not web_search.get("fundamentals_error")):
        failed.append("recent news")
    return failed


def _evidence_gaps(icp_profile: dict, technology: dict, hiring: dict, web_search: dict) -> list[str]:
    """ICP criteria the seller specified but no source produced evidence for."""
    signals = web_search.get("company_signals") or {}
    gaps = []
    if icp_profile.get("target_company_size") and signals.get("headcount_range") in _UNKNOWN:
        gaps.append("company size")
    if icp_profile.get("funding_stage") and signals.get("funding_stage") in _UNKNOWN:
        gaps.append("funding stage")
    if icp_profile.get("tech_signals") and not any((technology.get("technologies") or {}).values()):
        gaps.append("technology")
    if icp_profile.get("hiring_signals") and not hiring.get("open_positions"):
        gaps.append("hiring roles")
    if icp_profile.get("budget_indicator") and signals.get("revenue_estimate") in _UNKNOWN and signals.get("funding_stage") in _UNKNOWN:
        gaps.append("budget")
    return gaps


def assess_coverage(icp_profile: dict, technology: dict, hiring: dict, web_search: dict) -> dict:
    """Return the highest confidence the evidence supports, with the reasons."""
    failed = _failed_sources(technology, hiring, web_search)
    gaps = _evidence_gaps(icp_profile, technology, hiring, web_search)

    ceiling = "high"
    if len(failed) >= 2 or len(gaps) >= 3:
        ceiling = "low"
    elif failed or len(gaps) >= 2:
        ceiling = "medium"

    return {"ceiling": ceiling, "failed_sources": failed, "evidence_gaps": gaps}


def cap_confidence(model_confidence: str, coverage: dict) -> tuple[str, str | None]:
    """Cap the model's confidence at the coverage ceiling; return (confidence, note when capped)."""
    ceiling = coverage["ceiling"]
    if model_confidence not in _LEVELS or _LEVELS.index(model_confidence) <= _LEVELS.index(ceiling):
        return model_confidence, None
    reasons = []
    if coverage["failed_sources"]:
        reasons.append("couldn't retrieve " + ", ".join(coverage["failed_sources"]))
    if coverage["evidence_gaps"]:
        reasons.append("no evidence found for " + ", ".join(coverage["evidence_gaps"]))
    return ceiling, f"Confidence capped at {ceiling}: " + "; ".join(reasons) + "."
