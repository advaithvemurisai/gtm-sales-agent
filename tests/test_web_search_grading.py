from scripts.eval_web_search import _matches_word, grade


def _evidence(signals=None, tools=None, roles=None, tech_error=None):
    return {
        "technology": {"raw_data": {"technologies": {"backend": tools or []}, "error": tech_error, "source_urls": ["https://a"]}},
        "hiring": {"raw_data": {"open_positions": roles or [], "hiring_active": bool(roles), "source_urls": []}},
        "web_search": {"raw_data": {"company_signals": signals or {}, "source_urls": ["https://b"]}},
    }


CASE = {"funding_stage": ["Public"], "headcount_range": ["1000+"], "founded_year": [2010],
        "headquarters": ["New York"], "tech_any": ["Go"], "hiring_active": True}
FICTIONAL = {"funding_stage": ["Unknown"], "headcount_range": ["Unknown"], "founded_year": [None],
             "headquarters": [None], "tech_any": [], "hiring_active": False}


def test_word_match_does_not_hit_substrings():
    assert _matches_word("Go", "Go")
    assert _matches_word("Go", "Go (Golang)")
    assert not _matches_word("Go", "Google Cloud")
    assert not _matches_word("Go", "Django")
    assert _matches_word("C++", "C++")
    assert _matches_word("Next.js", "Next.js")


def test_correct_research_scores_every_field():
    signals = {"funding_stage": "Public", "headcount_range": "1000+", "founded_year": 2010, "headquarters": "New York, NY"}
    result = grade(CASE, _evidence(signals, ["Go", "Python"], ["SRE"]))

    assert all(result["fields"].values())


def test_failed_source_counts_as_wrong_not_skipped():
    result = grade(CASE, _evidence(tech_error="timeout"))

    assert result["fields"]["technology"] is False
    assert result["errors"] == {"technology": "timeout"}


def test_fictional_company_with_invented_facts_fails():
    signals = {"funding_stage": "Series A", "headcount_range": "11-50", "founded_year": 2019, "headquarters": "Austin"}
    result = grade(FICTIONAL, _evidence(signals, ["React"], ["Engineer"]))

    assert not any(result["fields"].values())


def test_fictional_company_with_nothing_found_passes():
    signals = {"funding_stage": "Unknown", "headcount_range": "Unknown", "founded_year": None, "headquarters": None}

    assert all(grade(FICTIONAL, _evidence(signals))["fields"].values())


def test_headcount_is_bucketed_into_schema_ranges():
    from backend.tools.web_search import headcount_range

    assert [headcount_range(n) for n in (None, 0, 6, 50, 51, 141, 500, 800, 16622)] == [
        "Unknown", "Unknown", "1-10", "11-50", "51-200", "51-200", "201-500", "501-1000", "1000+"]
