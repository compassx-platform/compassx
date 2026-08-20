"""Observability Connection Providers (Loki, Prometheus)."""

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


class LokiProvider(BaseConnectionProvider):
    @property
    def type_id(self) -> str:
        return "loki"

    @property
    def name(self) -> str:
        return "Grafana Loki"

    @property
    def category(self) -> str:
        return "observability"

    @property
    def description(self) -> str:
        return "Connect to Grafana Loki log aggregation system for query_range log streaming."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 3100

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="base_url", label="Loki Base URL", placeholder="http://loki:3100 or https://logs.example.com", required=True),
            ConnectionFieldDefinition(name="org_id", label="Tenant / Org ID (X-Scope-OrgID)", placeholder="tenant1", required=False),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="token", label="Bearer Token / API Key", type="password", placeholder="ey...", required=False),
            ConnectionFieldDefinition(name="username", label="Basic Auth Username", required=False),
            ConnectionFieldDefinition(name="password", label="Basic Auth Password", type="password", required=False),
        ]

    def build_client(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionClient:
        base_url = config.get("base_url", "").rstrip("/")
        auth = dict(auth_config or {})
        org_id = config.get("org_id")
        if org_id:
            headers = auth.setdefault("headers", {})
            headers["X-Scope-OrgID"] = org_id

        return ConnectionClient(
            name=config.get("name", "loki"),
            base_url=base_url,
            auth_config=auth,
            connector_type="loki",
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
            test_url = f"{base_url}/ready"
            with httpx.Client(timeout=10.0, headers=client.headers) as http:
                try:
                    resp = http.get(test_url)
                except httpx.HTTPError:
                    # Fallback to labels endpoint
                    resp = http.get(f"{base_url}/loki/api/v1/labels")

            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code in (200, 204):
                return ConnectionTestResult(
                    success=True,
                    message=f"Loki server is ready ({latency_ms}ms)",
                    latency_ms=latency_ms,
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Loki server returned HTTP {resp.status_code}",
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                message=f"Loki connection test failed: {str(exc)}",
                latency_ms=latency_ms,
            )


class PrometheusProvider(BaseConnectionProvider):
    @property
    def type_id(self) -> str:
        return "prometheus"

    @property
    def name(self) -> str:
        return "Prometheus"

    @property
    def category(self) -> str:
        return "observability"

    @property
    def description(self) -> str:
        return "Connect to Prometheus monitoring server for metrics querying."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 9090

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="base_url", label="Prometheus Base URL", placeholder="http://prometheus:9090", required=True),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="token", label="Bearer Token", type="password", required=False),
            ConnectionFieldDefinition(name="username", label="Basic Auth Username", required=False),
            ConnectionFieldDefinition(name="password", label="Basic Auth Password", type="password", required=False),
        ]

    def build_client(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionClient:
        base_url = config.get("base_url", "").rstrip("/")
        return ConnectionClient(
            name=config.get("name", "prometheus"),
            base_url=base_url,
            auth_config=auth_config,
            connector_type="prometheus",
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
            test_url = f"{base_url}/-/ready"
            with httpx.Client(timeout=10.0, headers=client.headers) as http:
                try:
                    resp = http.get(test_url)
                except httpx.HTTPError:
                    resp = http.get(f"{base_url}/api/v1/status/runtimeinfo")

            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code in (200, 204):
                return ConnectionTestResult(
                    success=True,
                    message=f"Prometheus server is ready ({latency_ms}ms)",
                    latency_ms=latency_ms,
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Prometheus server returned HTTP {resp.status_code}",
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                message=f"Prometheus connection test failed: {str(exc)}",
                latency_ms=latency_ms,
            )
