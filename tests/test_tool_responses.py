import json
from types import SimpleNamespace

import pytest

from backend.agent import evidence_cache
from backend.agent.pipeline import run_evaluation_pipeline
from backend.llm import generate_json, response_text, run_web_search
from backend.tools import hiring_signals, tech_signals, web_search


class QueueClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = self
        self.calls = []

    def with_options(self, **kwargs):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)


def text_block(text, citations=None):
    return SimpleNamespace(type="text", text=text, citations=citations)


def citation(url):
    return SimpleNamespace(url=url)


def message(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=None)


def test_tools_accept_text_blocks_without_citations(monkeypatch):
    search_response = message(text_block("Search result", None))
    json_response = message(text_block("{}"))
    monkeypatch.setattr(web_search, "parse_company_signals", lambda *args: {})

    monkeypatch.setattr(web_search, "get_client", lambda: QueueClient([
        search_response,
        search_response,
        json_response,
    ]))
    web_result = web_search.get_web_search_data("Example")
    assert web_result["raw_data"]["error"] is None

    monkeypatch.setattr(tech_signals, "get_client", lambda: QueueClient([search_response]))
    monkeypatch.setattr(tech_signals, "_extract_tech_stack", lambda *args: {})
    assert tech_signals.get_tech_signals("Example")["raw_data"]["error"] is None

    monkeypatch.setattr(hiring_signals, "get_client", lambda: QueueClient([search_response]))
    monkeypatch.setattr(hiring_signals, "_extract_hiring_fields", lambda *args: {})
    assert hiring_signals.get_hiring_signals("Example")["raw_data"]["error"] is None


def test_web_search_keeps_uncited_text_and_collects_citations():
    client = QueueClient([message(
        text_block("I'll look that up."),
        text_block("Acme has 250 employees.", [citation("https://example.com/a")]),
        text_block("It raised a Series B.", [citation("https://example.com/b"), citation("https://example.com/a")]),
    )])

    text, urls = run_web_search(client, "query", SimpleNamespace(info=lambda *a, **k: None), "test")

    assert "Acme has 250 employees." in text
    assert "I'll look that up." in text
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_web_search_resumes_paused_turns():
    client = QueueClient([
        message(text_block("Part one."), stop_reason="pause_turn"),
        message(text_block("Part two.")),
    ])

    text, _ = run_web_search(client, "query", SimpleNamespace(info=lambda *a, **k: None), "test")

    assert text == "Part one. Part two."
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-1]["role"] == "assistant"


def test_response_text_skips_thinking_blocks():
    response = message(SimpleNamespace(type="thinking", thinking=""), text_block("Answer"))

    assert response_text(response) == "Answer"


def _stub_sources(monkeypatch, calls=None, web_error=None):
    def count(name, result):
        def fn(company, website=None):
            if calls is not None:
                calls.append(name)
            return result
        return fn

    monkeypatch.setattr("backend.agent.pipeline.get_tech_signals", count("tech", {
        "raw_data": {"technologies": {}, "source_urls": ["https://a.example/stack"], "error": None}, "summary": None,
    }))
    monkeypatch.setattr("backend.agent.pipeline.get_hiring_signals", count("hiring", {
        "raw_data": {"open_positions": [], "source_urls": [], "error": None}, "summary": None,
    }))
    monkeypatch.setattr("backend.agent.pipeline.get_web_search_data", count("web", {
        "raw_data": {
            "fundamentals": "fundamentals text", "news": "news text", "company_signals": {},
            "source_urls": ["https://b.example/about"], "error": web_error,
        },
        "summary": None,
    }))


def _verdict_client(monkeypatch, **overrides):
    verdict = {
        "decision": "WATCH", "confidence": "high", "reasoning": "Evidence is incomplete.",
        "signals": [{"text": "Web search failed", "source_ids": [1, 99]}], "next_step": "Verify funding.",
        "criteria": [{"criterion": "Company size", "status": "unknown", "evidence": "none", "source_ids": [2]}],
        **overrides,
    }
    client = QueueClient([message(SimpleNamespace(type="thinking", thinking=""), text_block(json.dumps(verdict)))] * 5)
    monkeypatch.setattr("backend.agent.pipeline.get_client", lambda: client)
    return client


@pytest.fixture(autouse=True)
def _clear_cache():
    evidence_cache.clear()


def test_pipeline_caps_confidence_and_validates_citations(monkeypatch):
    _stub_sources(monkeypatch, web_error="web search unavailable")
    client = _verdict_client(monkeypatch)

    result = run_evaluation_pipeline("Example", {"raw_description": "analytics", "target_company_size": "50-500"})

    assert result["verdict"]["decision"] == "WATCH"
    # The model claimed "high", but both web searches failed and size has no evidence, so the code caps it.
    assert result["verdict"]["model_confidence"] == "high"
    assert result["verdict"]["confidence"] == "low"
    assert "Confidence capped" in result["verdict"]["confidence_note"]
    # Source 99 doesn't exist (two URLs were cited), so it is dropped.
    assert result["verdict"]["signals"][0]["source_ids"] == [1]
    assert [s["id"] for s in result["sources"]] == [1, 2]
    # One verdict call per run: no per-source summarize calls.
    assert len(client.calls) == 1
    assert client.calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert "SOURCE FAILED" in client.calls[0]["messages"][0]["content"]


def test_rerun_reuses_cached_evidence_and_only_regenerates_the_verdict(monkeypatch):
    calls = []
    _stub_sources(monkeypatch, calls)
    client = _verdict_client(monkeypatch)

    run_evaluation_pipeline("Example Inc", {"raw_description": "a"}, "https://www.example.com/")
    run_evaluation_pipeline("  example inc", {"raw_description": "a", "funding_stage": ["Seed"]}, "example.com")

    assert sorted(calls) == ["hiring", "tech", "web"]
    assert len(client.calls) == 2


def test_failed_evidence_is_not_cached(monkeypatch):
    calls = []
    _stub_sources(monkeypatch, calls, web_error="boom")
    _verdict_client(monkeypatch)

    run_evaluation_pipeline("Example", {"raw_description": "a"})
    run_evaluation_pipeline("Example", {"raw_description": "a"})

    assert calls.count("web") == 2


def test_news_failure_keeps_fundamentals(monkeypatch):
    def fake_search(client, query, logger, operation):
        if operation == "web_search.news":
            raise TimeoutError("news timed out")
        return "Acme has 120 employees.", ["https://example.com/a"]

    monkeypatch.setattr(web_search, "get_client", lambda: object())
    monkeypatch.setattr(web_search, "run_web_search", fake_search)
    monkeypatch.setattr(web_search, "parse_company_signals", lambda *args: {"funding_stage": "Series A"})

    data = web_search.get_web_search_data("Acme")["raw_data"]

    assert data["fundamentals"] == "Acme has 120 employees."
    assert data["company_signals"] == {"funding_stage": "Series A"}
    assert data["news_error"] == "news timed out"
    assert data["fundamentals_error"] is None
    assert data["error"] is None


def test_extractor_parse_failure_reports_source_error(monkeypatch):
    monkeypatch.setattr(hiring_signals, "get_client", lambda: QueueClient([message(text_block("Roles found."))]))
    monkeypatch.setattr(hiring_signals, "generate_json", lambda *a, **k: json.loads("not json"))
    hiring = hiring_signals.get_hiring_signals("Example")["raw_data"]

    monkeypatch.setattr(tech_signals, "get_client", lambda: QueueClient([message(text_block("Stack."))]))
    monkeypatch.setattr(tech_signals, "generate_json", lambda *a, **k: json.loads("not json"))
    tech = tech_signals.get_tech_signals("Example")["raw_data"]

    assert hiring["error"] and hiring["hiring_active"] is False
    assert tech["error"] and tech["technologies"] == {}


def test_generate_json_rejects_refusals():
    client = QueueClient([message(text_block(""), stop_reason="refusal")])

    with pytest.raises(ValueError, match="refusal"):
        generate_json(client, model="m", prompt="p", schema={}, operation="op", logger=SimpleNamespace(info=lambda *a, **k: None))
