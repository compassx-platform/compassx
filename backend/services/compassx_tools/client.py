"""Connection client helper for external services (Loki, Prometheus, REST APIs)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Mapping
import httpx


class ConnectionUnreachableError(Exception):
    """Raised when an external connection target is unreachable."""
    pass


class ConnectionClient:
    """Client for querying external systems with injected credentials."""

    def __init__(
        self,
        name: str,
        base_url: str,
        auth_config: Any = None,
        connector_type: str = "custom",
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.connector_type = connector_type.lower() if connector_type else "custom"
        self.auth_config = auth_config or {}
        if isinstance(self.auth_config, str):
            try:
                self.auth_config = json.loads(self.auth_config)
            except Exception:
                pass
        self._headers = self._build_headers()

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._headers)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if isinstance(self.auth_config, dict):
            # Support explicit headers dictionary
            if "headers" in self.auth_config and isinstance(self.auth_config["headers"], dict):
                headers.update(self.auth_config["headers"])

            # Support Bearer token / api_key
            if "token" in self.auth_config:
                headers["Authorization"] = f"Bearer {self.auth_config['token']}"
            elif "api_key" in self.auth_config:
                headers["Authorization"] = f"Bearer {self.auth_config['api_key']}"
            elif "apiKey" in self.auth_config:
                headers["Authorization"] = f"Bearer {self.auth_config['apiKey']}"

            # Support Basic auth header if username/password provided
            if "username" in self.auth_config and "password" in self.auth_config:
                import base64
                cred = f"{self.auth_config['username']}:{self.auth_config['password']}"
                headers["Authorization"] = f"Basic {base64.b64encode(cred.encode()).decode()}"
        elif isinstance(self.auth_config, str) and self.auth_config:
            if self.auth_config.startswith("Bearer ") or self.auth_config.startswith("Basic "):
                headers["Authorization"] = self.auth_config
            else:
                headers["Authorization"] = f"Bearer {self.auth_config}"

        return headers

    def _resolve_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        timeout: float = 30.0,
        verify: bool = False,
    ) -> httpx.Response:
        url = self._resolve_url(path)
        try:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                resp = client.get(url, params=params, headers=self._headers)
                return resp
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
            raise ConnectionUnreachableError(f"Failed to connect to {self.name} at {url}: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionUnreachableError(f"HTTP request error connecting to {self.name}: {exc}") from exc

    def post(
        self,
        path: str,
        json: Any = None,
        data: Any = None,
        params: Mapping[str, Any] | None = None,
        timeout: float = 30.0,
        verify: bool = False,
    ) -> httpx.Response:
        url = self._resolve_url(path)
        try:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                resp = client.post(url, json=json, data=data, params=params, headers=self._headers)
                return resp
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
            raise ConnectionUnreachableError(f"Failed to connect to {self.name} at {url}: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionUnreachableError(f"HTTP request error connecting to {self.name}: {exc}") from exc

    def query_range(
        self,
        query: str,
        minutes: int = 5,
        start: str | int | None = None,
        end: str | int | None = None,
        limit: int = 100,
    ) -> str:
        """Query Loki range endpoint (/loki/api/v1/query_range).

        Returns extracted log lines formatted as text.
        """
        now = time.time()
        if end is None:
            end_ns = int(now * 1e9)
        elif isinstance(end, (int, float)):
            end_ns = int(end if end > 1e11 else end * 1e9)
        else:
            end_ns = str(end)

        if start is None:
            start_ns = int((now - minutes * 60) * 1e9)
        elif isinstance(start, (int, float)):
            start_ns = int(start if start > 1e11 else start * 1e9)
        else:
            start_ns = str(start)

        params = {
            "query": query,
            "start": str(start_ns),
            "end": str(end_ns),
            "limit": str(limit),
        }

        resp = self.get("loki/api/v1/query_range", params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"Loki query returned error {resp.status_code}: {resp.text}")

        data = resp.json()
        status = data.get("status")
        if status != "success":
            raise RuntimeError(f"Loki query failed: {data.get('error', 'unknown error')}")

        result = data.get("data", {}).get("result", [])
        if not result:
            return "No logs found matching query."

        lines = []
        for stream in result:
            values = stream.get("values", [])
            for entry in values:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    ts_ns, line_text = entry[0], entry[1]
                    try:
                        ts_sec = int(ts_ns) / 1e9
                        ts_dt = datetime.fromtimestamp(ts_sec, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                        lines.append(f"[{ts_dt}] {line_text}")
                    except Exception:
                        lines.append(f"[{ts_ns}] {line_text}")
                else:
                    lines.append(str(entry))

        return "\n".join(lines)
