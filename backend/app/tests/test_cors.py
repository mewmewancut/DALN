import runpy
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings


def test_cors_uses_configured_frontend_origin_and_rejects_other_websites(monkeypatch):
    settings = get_settings().model_copy(
        update={"frontend_public_url": "http://127.0.0.1:5174/store"}
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    app = runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))["app"]
    client = TestClient(app)
    headers = {
        "Origin": "http://127.0.0.1:5174",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    response = client.options("/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    response = client.options("/auth/login", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
