"""Convenience endpoint lookup for legacy config classes.

Config classes (airflow/EG/minio/storage) call resolve_url()/resolve()
instead of hardcoding if-local-else-k8s-DNS logic. Explicit env-var
overrides in those classes still win — this is only the default path.

Uses a module-level lazily-built registry (one per process, derived from
COMPASSX_PLATFORM_PROFILE). Rebuild with reset_registry() in tests.
"""

from __future__ import annotations

import os

from compassx.models import ServiceEndpoint, ServiceNotFoundError

_registry = None


def get_registry():
    global _registry
    if _registry is None:
        from compassx.registry import YamlServiceRegistry, load_profile

        _registry = YamlServiceRegistry.from_files(load_profile())
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None


def resolve(name: str) -> ServiceEndpoint:
    return get_registry().get_service(name)


def resolve_url(name: str, *, protocol: str | None = None) -> str:
    endpoint = resolve(name)
    if protocol:
        return f"{protocol}://{endpoint.address}"
    return endpoint.base_url


def try_resolve_url(name: str, fallback: str, *, protocol: str | None = None) -> str:
    """Resolve or return fallback (keeps legacy behavior if registry
    misconfigured — never crash config import)."""
    try:
        return resolve_url(name, protocol=protocol)
    except (ServiceNotFoundError, Exception):  # noqa: BLE001 - config must not crash
        return fallback


def try_resolve_url_container(name: str, fallback: str) -> str:
    """Resolve from container perspective — for URLs injected into pods/kernels.

    In kubernetes mode this returns the cluster-internal DNS URL.
    In docker mode this returns the docker-network hostname.
    Falls back to *fallback* if the registry is not configured.
    """
    try:
        from compassx.registry import YamlServiceRegistry, load_profile

        profile = load_profile()
        registry = YamlServiceRegistry.from_files(profile, perspective="container")
        endpoint = registry.get_service(name)
        # A container cannot reach a host-local service through localhost.
        # In local-dev the backend runs on the host while notebook kernels run
        # inside Docker, so rewrite localhost/127.0.0.1 to the host gateway.
        if endpoint.host in {"localhost", "127.0.0.1"}:
            host_gateway = os.environ.get("COMPASSX_HOST_GATEWAY", "host.docker.internal")
            return endpoint.base_url.replace(endpoint.host, host_gateway, 1)
        return endpoint.base_url
    except (ServiceNotFoundError, Exception):  # noqa: BLE001
        return fallback
