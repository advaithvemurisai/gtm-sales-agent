from backend.llm import get_client


def test_client_sends_workspace_header_only_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    assert "anthropic-workspace-id" not in get_client().default_headers

    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_123")
    assert get_client().default_headers["anthropic-workspace-id"] == "wrkspc_123"


def test_search_text_joins_cited_fragments_without_spaces():
    from types import SimpleNamespace as NS

    from backend.llm import _join_text

    content = [
        NS(type="text", text="I'll look that up."),
        NS(type="server_tool_use"),
        NS(type="web_search_tool_result"),
        NS(type="text", text="Series B. GV led it"),
        NS(type="text", text="."),
        NS(type="text", text=" Founded in 2017 ("),
        NS(type="text", text="PitchBook"),
        NS(type="text", text=")."),
    ]

    assert _join_text(content) == "I'll look that up.\n\nSeries B. GV led it. Founded in 2017 (PitchBook)."
