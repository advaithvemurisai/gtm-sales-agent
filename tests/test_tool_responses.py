from types import SimpleNamespace

from backend.agent.pipeline import _summarize_tool_result, run_evaluation_pipeline
from backend.llm import response_text, run_web_search
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


def test_pipeline_handles_string_search_results_and_parent_failure(monkeypatch):
    assert "SOURCE FAILED" in _summarize_tool_result(
        {"raw_data": "fundamentals text", "error": "search unavailable"},
        "Company Fundamentals",
        "system",
    )

    monkeypatch.setattr("backend.agent.pipeline.get_tech_signals", lambda name: {
        "raw_data": {"technologies": {}, "error": None}, "summary": None,
    })
    monkeypatch.setattr("backend.agent.pipeline.get_hiring_signals", lambda name: {
        "raw_data": {"open_positions": [], "error": None}, "summary": None,
    })
    monkeypatch.setattr("backend.agent.pipeline.get_web_search_data", lambda name: {
        "raw_data": {
            "fundamentals": "fundamentals text",
            "news": "news text",
            "company_signals": {},
            "error": "web search unavailable",
        },
        "summary": None,
    })
    verdict_response = message(
        SimpleNamespace(type="thinking", thinking=""),
        text_block("VERDICT: WATCH\nREASONING: Evidence is incomplete.\nKEY SIGNALS:\n- Web search failed\nCONFIDENCE: LOW"),
    )
    fake_client = QueueClient([
        message(text_block("Summary")),
        message(text_block("Summary")),
        verdict_response,
    ])
    monkeypatch.setattr("backend.agent.pipeline.get_client", lambda: fake_client)

    result = run_evaluation_pipeline("Example", {"raw_description": "analytics"})

    assert result["web_search"]["summary"].splitlines()[0].startswith("SOURCE FAILED")
    assert result["verdict"]["decision"] == "WATCH"
    assert result["verdict"]["confidence"] == "low"
