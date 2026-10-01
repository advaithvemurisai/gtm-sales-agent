from backend.llm import get_client


def test_client_sends_workspace_header_only_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    assert "anthropic-workspace-id" not in get_client().default_headers

    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_123")
    assert get_client().default_headers["anthropic-workspace-id"] == "wrkspc_123"
