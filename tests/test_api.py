from fastapi.testclient import TestClient

from backend.app import app


def test_analyze_rejects_oversized_product_description():
    client = TestClient(app)
    response = client.post("/analyze", json={
        "company_name": "Example",
        "product_description": "x" * 2001,
    })

    assert response.status_code == 422


def test_analyze_hides_internal_errors(monkeypatch):
    monkeypatch.setattr("backend.app.infer_icp_signals", lambda description: {})
    monkeypatch.setattr(
        "backend.app.run_evaluation_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret provider detail")),
    )
    client = TestClient(app)
    response = client.post("/analyze", json={
        "company_name": "Example",
        "product_description": "B2B analytics",
    })

    assert response.status_code == 500
    assert response.json()["detail"] == "Analysis failed. Check the server logs for details."


def test_analyze_has_a_rate_limit(monkeypatch):
    monkeypatch.setattr("backend.app._request_windows", {"analyze": __import__("collections").deque()})
    monkeypatch.setattr("backend.app.infer_icp_signals", lambda description: {})
    monkeypatch.setattr("backend.app.run_evaluation_pipeline", lambda **kwargs: {
        "web_search": {"raw_data": {"company_signals": {}, "fundamentals": "", "news": ""}, "summary": ""},
        "technology": {"raw_data": {}, "summary": ""},
        "hiring": {"raw_data": {}, "summary": ""},
        "verdict": {"decision": "WATCH", "reasoning": "Limited evidence.", "signals": []},
    })
    client = TestClient(app)
    payload = {"company_name": "Example", "product_description": "B2B analytics"}
    for _ in range(5):
        client.post("/analyze", json=payload)

    response = client.post("/analyze", json=payload)
    assert response.status_code == 429

def test_rate_limit_is_per_client_and_forgets_idle_clients(monkeypatch):
    from backend import app as app_module

    monkeypatch.setattr(app_module, "_request_windows", {})
    for _ in range(app_module._RATE_LIMIT):
        assert app_module._allow_request("10.0.0.1", 0.0)
    assert not app_module._allow_request("10.0.0.1", 1.0)
    assert app_module._allow_request("10.0.0.2", 1.0)

    later = app_module._RATE_WINDOW_SECONDS + 5.0
    assert app_module._allow_request("10.0.0.3", later)
    assert set(app_module._request_windows) == {"10.0.0.3"}
