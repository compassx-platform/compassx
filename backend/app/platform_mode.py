"""HTTP guards for services left out of the active deployment mode."""

from __future__ import annotations

from fastapi import HTTPException

from compassx.registry.deployment_mode import load_deployment_mode


def ensure_deployed(service: str) -> None:
    """Raise 503 when ``service`` is not part of the active deployment mode."""
    mode = load_deployment_mode()
    if not mode.includes(service):
        raise HTTPException(status_code=503, detail=mode.unavailable_reason(service))


def require_deployed(service: str):
    """FastAPI dependency that rejects calls to a service this mode did not start."""

    def _dependency() -> None:
        ensure_deployed(service)

    return _dependency
