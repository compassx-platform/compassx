"""REST API and Webhook Connection Providers."""

from __future__ import annotations

import time
from typing import Any, List, Optional
import httpx

from app.catalog.connections.base_provider import (
    BaseConnectionProvider,
    ConnectionFieldDefinition,
    ConnectionTestResult,
)
from services.compassx_tools.client import ConnectionClient


class RestApiProvider(BaseConnectionProvider):
    @property
    def type_id(self) -> str:
        return "rest_api"

    @property
    def name(self) -> str:
        return "REST API"

    @property
    def category(self) -> str:
        return "api"

    @property
    def description(self) -> str:
        return "Connect to any external REST API with Bearer, API Key, Basic Auth, or Custom Headers."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="base_url", label="Base URL", placeholder="https://api.example.com/v1", required=True),
            ConnectionFieldDefinition(name="timeout_seconds", label="Timeout (seconds)", type="number", default=30, required=False),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(
                name="auth_type",
                label="Authentication Type",
                type="select",
                default="bearer",
                required=True,
                options=[
                    {"value": "bearer", "label": "Bearer Token"},
                    {"value": "api_key", "label": "API Key Header"},
                    {"value": "basic", "label": "Basic Auth (Username / Password)"},
                    {"value": "custom", "label": "Custom Headers JSON"},
                    {"value": "none", "label": "No Auth (Public)"},
                ],
            ),
            ConnectionFieldDefinition(name="token", label="Bearer Token", type="password", placeholder="ey... or secret token", required=False),
            ConnectionFieldDefinition(name="api_key_name", label="API Key Header Name", default="X-API-Key", placeholder="X-API-Key", required=False),
            ConnectionFieldDefinition(name="api_key_value", label="API Key Value", type="password", placeholder="key_...", required=False),
            ConnectionFieldDefinition(name="username", label="Basic Auth Username", required=False),
            ConnectionFieldDefinition(name="password", label="Basic Auth Password", type="password", required=False),
            ConnectionFieldDefinition(name="custom_headers", label="Custom Headers JSON", type="textarea", placeholder='{"X-Custom": "val"}', required=False),
        ]

    def _normalize_auth(self, auth_config: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not auth_config:
            return {}
        auth_type = auth_config.get("auth_type", "bearer")
        if auth_type == "bearer" and auth_config.get("token"):
            return {"token": auth_config["token"]}
        if auth_type == "api_key" and auth_config.get("api_key_value"):
            hdr = auth_config.get("api_key_name", "X-API-Key")
            return {"headers": {hdr: auth_config["api_key_value"]}}
        if auth_type == "basic":
            return {"username": auth_config.get("username", ""), "password": auth_config.get("password", "")}
        if auth_type == "custom" and auth_config.get("custom_headers"):
            headers = auth_config["custom_headers"]
            if isinstance(headers, str):
                import json
                try:
                    headers = json.loads(headers)
                except Exception:
                    headers = {}
            return {"headers": headers}
        return auth_config

    def build_client(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionClient:
        base_url = config.get("base_url", "")
        auth = self._normalize_auth(auth_config)
        return ConnectionClient(
            name=config.get("name", "rest_api"),
            base_url=base_url,
            auth_config=auth,
            connector_type="rest_api",
        )

    def test_connection(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionTestResult:
        base_url = config.get("base_url", "").rstrip("/")
        if not base_url:
            return ConnectionTestResult(success=False, message="Base URL is required")

        start = time.time()
        try:
            client = self.build_client(config, auth_config)
            # Try HEAD or GET with short timeout
            with httpx.Client(timeout=10.0, headers=client.headers) as http:
                try:
                    resp = http.get(base_url)
                except httpx.HTTPStatusError as e:
                    resp = e.response

            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code < 500:
                return ConnectionTestResult(
                    success=True,
                    message=f"Connected to {base_url} (HTTP {resp.status_code})",
                    latency_ms=latency_ms,
                    details={"status_code": resp.status_code},
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Server returned HTTP error {resp.status_code}",
                    latency_ms=latency_ms,
                    details={"status_code": resp.status_code},
                )
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {str(exc)}",
                latency_ms=latency_ms,
            )


class CustomWebhookProvider(RestApiProvider):
    @property
    def type_id(self) -> str:
        return "custom"

    @property
    def name(self) -> str:
        return "Custom Webhook / Service"

    @property
    def description(self) -> str:
        return "Connect to custom webhook endpoints, internal services, and microservices."

    @property
    def is_popular(self) -> bool:
        return False
