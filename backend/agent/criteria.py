"""Map the verdict's criteria scorecard onto the ICP fields the seller specified.

The verdict schema can't require one entry per specified criterion, and the model occasionally returns a
truncated scorecard (one real entry plus a blank or "placeholder" row). These helpers detect that so the
pipeline can retry, and fill any gap that survives the retry with an explicit unknown entry.
"""

ICP_FIELDS = {
    "size": "target_company_size",
    "funding": "funding_stage",
    "technology": "tech_signals",
    "hiring": "hiring_signals",
    "budget": "budget_indicator",
}
LABELS = {
    "size": "Company size",
    "funding": "Funding stage",
    "technology": "Technology",
    "hiring": "Hiring roles",
    "budget": "Budget",
}
# Checked in order: "budget" before "size" so "budget (company size)" style names map to budget.
_KEYWORDS = (
    ("budget", ("budget", "revenue")),
    ("funding", ("fund",)),
    ("size", ("size", "headcount", "employee")),
    ("hiring", ("hir", "role")),
    ("technology", ("tech", "stack", "tool")),
)

_JUNK_NAMES = {"", "placeholder", "criterion", "n/a", "na", "none", "tbd", "-"}


def criterion_key(name: str) -> str | None:
    lowered = (name or "").lower()
    for key, words in _KEYWORDS:
        if any(word in lowered for word in words):
            return key
    return None


def _is_junk(name: str) -> bool:
    return (name or "").strip().lower() in _JUNK_NAMES


def specified_keys(icp_profile: dict) -> list[str]:
    return [key for key, field in ICP_FIELDS.items() if icp_profile.get(field)]


def missing_criteria(verdict: dict, icp_profile: dict) -> list[str]:
    """Specified criteria with no scorecard entry, or a scorecard containing an unnamed row."""
    criteria = verdict.get("criteria") or []
    present = {criterion_key(item.get("criterion", "")) for item in criteria}
    missing = [key for key in specified_keys(icp_profile) if key not in present]
    if any(_is_junk(item.get("criterion", "")) for item in criteria):
        missing.append("unnamed")
    return missing


def repair_criteria(verdict: dict, icp_profile: dict) -> None:
    """Drop blank or placeholder rows and add an unknown entry for each specified criterion still missing."""
    criteria = [item for item in verdict.get("criteria") or [] if not _is_junk(item.get("criterion", ""))]
    present = {criterion_key(item["criterion"]) for item in criteria}
    for key in specified_keys(icp_profile):
        if key not in present:
            criteria.append({"criterion": LABELS[key], "status": "unknown",
                             "evidence": "Not assessed in this verdict.", "source_ids": []})
    verdict["criteria"] = criteria
