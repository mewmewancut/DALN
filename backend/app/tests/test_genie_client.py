import httpx
import pytest
from fastapi import HTTPException

from app.services.genie_client import GenieClient


def test_oauth_is_cached_per_principal_and_api_bearer_never_contains_client_secret(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/oidc/v1/token":
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(200, json={"access_token": "fake-access", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer fake-access"
        assert "fake-secret" not in str(request.url) and b"fake-secret" not in request.content
        return httpx.Response(200, json={"status": "ASKING_AI"})

    real = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(handle), **kwargs)
    )
    client = GenieClient("https://fake.cloud.databricks.com", "fake-client", "fake-secret")
    for _ in range(2):
        assert (
            client.request("POST", "1/start-conversation", {"content": "test"})["status"]
            == "ASKING_AI"
        )
    assert sum(r.url.path == "/oidc/v1/token" for r in calls) == 1


@pytest.mark.parametrize("status,code", [(401, 502), (403, 502), (500, 502), (429, 429)])
def test_http_errors_are_sanitized(monkeypatch, status, code):
    def handle(request):
        if request.url.path == "/oidc/v1/token":
            return httpx.Response(200, json={"access_token": "fake-access", "expires_in": 3600})
        return httpx.Response(status, json={"message": "fake-secret private SQL"})

    real = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(handle), **kwargs)
    )
    with pytest.raises(HTTPException) as caught:
        GenieClient("https://fake.cloud.databricks.com", "fake-client", "fake-secret").request(
            "GET", "message"
        )
    assert caught.value.status_code == code
    assert "fake-secret" not in caught.value.detail and "private SQL" not in caught.value.detail
