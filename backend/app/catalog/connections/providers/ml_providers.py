"""ML Platform Connection Providers (MLflow)."""

from __future__ import annotations

import time
from typing import Any, List, Optional
import httpx

from app.catalog.connections.base_provider import (
    BaseConnectionProvider,
    ConnectionFieldDefinition,
    ConnectionTestResult,
    format_exception_message,
)
from services.compassx_tools.client import ConnectionClient


class MlflowProvider(BaseConnectionProvider):
    @property
    def type_id(self) -> str:
        return "mlflow"

    @property
    def name(self) -> str:
        return "MLflow"

    @property
    def category(self) -> str:
        return "api"

    @property
    def description(self) -> str:
        return "Connect to an MLflow tracking server to log experiments/runs and manage the model registry."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 5000

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="base_url", label="MLflow Tracking URI", placeholder="http://mlflow:5000", required=True),
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
            name=config.get("name", "mlflow"),
            base_url=base_url,
            auth_config=auth_config,
            connector_type="mlflow",
        )

    def test_connection(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionTestResult:
        base_url = config.get("base_url", "").rstrip("/")
        if not base_url:
            return ConnectionTestResult(success=False, message="MLflow Tracking URI is required")

        start = time.time()
        try:
            client = self.build_client(config, auth_config)
            with httpx.Client(timeout=10.0, headers=client.headers) as http:
                resp = http.get(f"{base_url}/health")
                if resp.status_code == 404:
                    # Older servers without /health; a valid API listing confirms reachability.
                    resp = http.get(f"{base_url}/api/2.0/mlflow/experiments/search", params={"max_results": 1})

            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code in (200, 204):
                return ConnectionTestResult(
                    success=True,
                    message=f"MLflow server is reachable ({latency_ms}ms)",
                    latency_ms=latency_ms,
                )
            return ConnectionTestResult(
                success=False,
                message=f"MLflow server returned HTTP {resp.status_code}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                message=f"MLflow connection test failed: {format_exception_message(exc)}",
                latency_ms=latency_ms,
            )
