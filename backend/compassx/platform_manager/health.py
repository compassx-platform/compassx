"""Health checking with root-cause diagnostics.

Every failure is classified and translated into an actionable message so
users see *why* a service is unreachable (DNS, refused, timeout, auth,
bad response) and what to do about it — not a bare traceback.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Callable

from compassx.interfaces.registry import ServiceRegistry
from compassx.models import HealthCheckFailedError, ServiceEndpoint, ServiceNotFoundError

logger = logging.getLogger(__name__)

# Well-known HTTP health paths per service; fall back to TCP connect.
DEFAULT_HTTP_HEALTH_PATHS: dict[str, str] = {
    "backend": "/healthcheck",
    "minio": "/minio/health/live",
    "airflow": "/health",
    "enterprise-gateway": "/api",
    "jupyter-server": "/api",
    "prometheus": "/-/healthy",
    "frontend": "/",
}


@dataclass
class ServiceHealth:
    name: str
    healthy: bool
    endpoint: str = ""
    latency_ms: int | None = None
    cause: str = ""        # machine-readable: dns | refused | timeout | http-<code> | tls | unknown
    message: str = ""      # human-readable root cause + suggested fix
    attempts: int = 1


@dataclass
class HealthReport:
    services: list[ServiceHealth] = field(default_factory=list)

    @property
    def all_healthy(self) -> bool:
        return all(s.healthy for s in self.services)

    @property
    def unhealthy(self) -> list[ServiceHealth]:
        return [s for s in self.services if not s.healthy]

    def summary(self) -> str:
        lines = []
        for s in self.services:
            status = "OK" if s.healthy else "FAIL"
            extra = f" ({s.latency_ms}ms)" if s.latency_ms is not None else ""
            lines.append(f"[{status}] {s.name} {s.endpoint}{extra}")
            if not s.healthy and s.message:
                lines.append(f"       -> {s.message}")
        return "\n".join(lines)


def _diagnose_exception(name: str, endpoint: ServiceEndpoint, exc: BaseException) -> tuple[str, str]:
    """Classify a connection failure and produce an actionable message."""
    host_port = f"{endpoint.host}:{endpoint.port}"
    root: BaseException = exc
    while root.__cause__ is not None:
        root = root.__cause__

    if isinstance(root, socket.gaierror):
        return "dns", (
            f"Cannot resolve host '{endpoint.host}'. If running on the host, the "
            f"service mode for '{name}' may be wrong (docker/k8s hostname used "
            f"outside its network). Check the active deployment profile."
        )
    if isinstance(root, ConnectionRefusedError):
        return "refused", (
            f"Connection refused at {host_port}. Service '{name}' is not "
            f"listening — it may not be started yet. Run `compassx up` or check "
            f"`compassx status`."
        )
    if isinstance(
        root, (asyncio.TimeoutError, TimeoutError, socket.timeout, asyncio.CancelledError)
    ):
        return "timeout", (
            f"Timeout connecting to {host_port}. Service '{name}' may be "
            f"starting, overloaded, or blocked by a firewall/proxy."
        )
    if isinstance(root, OSError) and getattr(root, "winerror", None) == 10061:
        return "refused", (
            f"Connection refused at {host_port}. Service '{name}' is not "
            f"listening — run `compassx up` or check `compassx status`."
        )
    return "unknown", f"Failed to reach '{name}' at {host_port}: {root.__class__.__name__}: {root}"


class HealthChecker:
    """Registry-driven health checks with retry + diagnostics."""

    def __init__(
        self,
        registry: ServiceRegistry,
        *,
        http_paths: dict[str, str] | None = None,
        connect_timeout: float = 3.0,
        retries: int = 2,
        backoff: float = 0.5,
    ) -> None:
        self._registry = registry
        self._http_paths = {**DEFAULT_HTTP_HEALTH_PATHS, **(http_paths or {})}
        self._timeout = connect_timeout
        self._retries = retries
        self._backoff = backoff

    # ── single-service checks ────────────────────────────────────────────

    async def check_tcp(self, name: str, endpoint: ServiceEndpoint) -> ServiceHealth:
        started = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(endpoint.host, endpoint.port),
                timeout=self._timeout,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            return ServiceHealth(
                name=name,
                healthy=True,
                endpoint=endpoint.address,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - classified below
            cause, message = _diagnose_exception(name, endpoint, exc)
            return ServiceHealth(
                name=name,
                healthy=False,
                endpoint=endpoint.address,
                cause=cause,
                message=message,
            )

    async def check_http(
        self, name: str, endpoint: ServiceEndpoint, path: str
    ) -> ServiceHealth:
        import httpx

        url = f"{endpoint.base_url}{path}"
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                resp = await client.get(url)
            latency_ms = int((time.monotonic() - started) * 1000)
            # Any HTTP response means the service is up; 5xx means unhealthy.
            if resp.status_code >= 500:
                return ServiceHealth(
                    name=name,
                    healthy=False,
                    endpoint=url,
                    latency_ms=latency_ms,
                    cause=f"http-{resp.status_code}",
                    message=(
                        f"'{name}' responded {resp.status_code} at {url}. Service is "
                        f"reachable but failing internally — check its logs: "
                        f"`compassx logs {name}`."
                    ),
                )
            return ServiceHealth(
                name=name, healthy=True, endpoint=url, latency_ms=latency_ms
            )
        except httpx.HTTPError as exc:
            cause, message = _diagnose_exception(name, endpoint, exc)
            return ServiceHealth(
                name=name, healthy=False, endpoint=url, cause=cause, message=message
            )

    async def check_service(self, name: str) -> ServiceHealth:
        """Check one service with retries; report the last diagnosis."""
        try:
            endpoint = self._registry.get_service(name)
        except ServiceNotFoundError as exc:
            return ServiceHealth(
                name=name,
                healthy=False,
                cause="unregistered",
                message=str(exc),
            )

        path = self._http_paths.get(name)
        last: ServiceHealth | None = None
        for attempt in range(1, self._retries + 2):
            if path and endpoint.protocol in ("http", "https"):
                result = await self.check_http(name, endpoint, path)
            else:
                result = await self.check_tcp(name, endpoint)
            result.attempts = attempt
            if result.healthy:
                return result
            last = result
            if attempt <= self._retries:
                await asyncio.sleep(self._backoff * attempt)
        assert last is not None
        logger.warning(
            "health.check failed service=%s endpoint=%s cause=%s attempts=%s: %s",
            name,
            last.endpoint,
            last.cause,
            last.attempts,
            last.message,
        )
        return last

    # ── aggregate checks ─────────────────────────────────────────────────

    async def check_all(self, services: list[str]) -> HealthReport:
        results = await asyncio.gather(*(self.check_service(s) for s in services))
        return HealthReport(services=list(results))

    async def wait_until_healthy(
        self,
        services: list[str],
        timeout: float = 120.0,
        interval: float = 3.0,
        on_progress: Callable[[HealthReport], None] | None = None,
    ) -> HealthReport:
        """Poll until all services healthy or timeout.

        Raises HealthCheckFailedError with a per-service root-cause summary.
        """
        deadline = time.monotonic() + timeout
        report = await self.check_all(services)
        while not report.all_healthy and time.monotonic() < deadline:
            if on_progress:
                on_progress(report)
            await asyncio.sleep(interval)
            report = await self.check_all(services)
        if not report.all_healthy:
            raise HealthCheckFailedError(
                "Platform services failed health checks after "
                f"{int(timeout)}s:\n{report.summary()}"
            )
        return report
