"""Bounded Genie REST requests with per-service-principal OAuth M2M authentication."""

import threading
import time
from functools import lru_cache

import httpx
from fastapi import HTTPException


class GenieClient:
    def __init__(self, host: str, client_id: str, client_secret: str):
        self.host = host
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = ""
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _authorize(self, client):
        with self._lock:
            if self._token and time.monotonic() < self._expires_at:
                return self._token
            response = client.post(
                f"{self.host}/oidc/v1/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials", "scope": "all-apis"},
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            lifetime = int(data.get("expires_in", 0))
            if not isinstance(token, str) or not token or lifetime <= 0:
                raise ValueError("Invalid OAuth response")
            self._token = token
            self._expires_at = time.monotonic() + max(0, lifetime - 60)
            return token

    def request(self, method: str, path: str, payload=None):
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.request(
                    method,
                    f"{self.host}/api/2.0/genie/spaces/{path}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._authorize(client)}"},
                )
                if response.status_code == 429:
                    raise HTTPException(429, "Genie đang quá tải. Vui lòng thử lại sau.")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid Genie response")
                return data
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise HTTPException(502, "Không thể kết nối Genie. Vui lòng thử lại sau.") from None


@lru_cache(maxsize=100)
def get_genie_client(host: str, client_id: str, client_secret: str) -> GenieClient:
    return GenieClient(host, client_id, client_secret)
