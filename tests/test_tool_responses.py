from types import SimpleNamespace

from backend.agent.pipeline import _summarize_tool_result, run_evaluation_pipeline
from backend.tools import builtwith, careers_scraper, web_search


class QueueClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = self

    def create(self, **kwargs):
        return next(self.responses)


def text_block(text, citations=None):
    return SimpleNamespace(type="text", text=text, citations=citations)


def test_tools_accept_text_blocks_without_citations(monkeypatch):
    search_response = SimpleNamespace(content=[text_block("Search result", None)])
    json_response = SimpleNamespace(content=[text_block("{}")])

    monkeypatch.setattr(web_search, "Anthropic", lambda **kwargs: QueueClient([
        search_response,
        search_response,
        json_response,
    ]))
    web_result = web_search.get_web_search_data("Example")
    assert web_result["raw_data"]["error"] is None

    monkeypatch.setattr(builtwith, "Anthropic", lambda **kwargs: QueueClient([
        search_response,
        json_response,
    ]))
    monkeypatch.setattr(builtwith, "_extract_tech_stack", lambda *args: {})
    assert builtwith.get_builtwith_data("Example")["raw_data"]["error"] is None

    monkeypatch.setattr(careers_scraper, "Anthropic", lambda **kwargs: QueueClient([
        search_response,
        json_response,
    ]))
    monkeypatch.setattr(careers_scraper, "_extract_hiring_fields", lambda *args: {})
    assert careers_scraper.get_careers_page_data("Example")["raw_data"]["error"] is None


def test_pipeline_handles_string_search_results_and_parent_failure(monkeypatch):
    assert "SOURCE FAILED" in _summarize_tool_result(
        {"raw_data": "fundamentals text", "error": "search unavailable"},
        "Company Fundamentals",
        "system",
    )

    monkeypatch.setattr("backend.agent.pipeline.get_builtwith_data", lambda name: {
        "raw_data": {"technologies": {}, "error": None}, "summary": None,
    })
    monkeypatch.setattr("backend.agent.pipeline.get_careers_page_data", lambda name: {
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
    verdict_response = SimpleNamespace(content=[text_block(
        "VERDICT: WATCH\nREASONING: Evidence is incomplete.\nKEY SIGNALS:\n- Web search failed\nCONFIDENCE: LOW"
    )])
    fake_client = QueueClient([
        SimpleNamespace(content=[text_block("Summary")]),
        SimpleNamespace(content=[text_block("Summary")]),
        verdict_response,
    ])
    monkeypatch.setattr("backend.agent.pipeline._get_client", lambda: fake_client)

    result = run_evaluation_pipeline("Example", {"raw_description": "analytics"})

    assert result["web_search"]["summary"].splitlines()[0].startswith("SOURCE FAILED")
    assert result["verdict"]["decision"] == "WATCH"