"""Auth dependency – returns static administrator credentials directly."""

from fastapi import Request

async def get_current_user(
    request: Request,
) -> dict:
    """
    Returns a static Admin user context directly.
    """
    return {
        "id": "bbbbbbbb-0000-0000-0000-000000000001",
        "sub": "bbbbbbbb-0000-0000-0000-000000000001",
        "email": "vishal@compass.internal",
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Vishalkumar Vora",
        "is_account_admin": True,
    }

# ── Platform layer (DI via app.state.platform) ───────────────────────────────

def get_platform(request: Request):
    """PlatformContainer wired during lifespan."""
    platform = getattr(request.app.state, "platform", None)
    if platform is None:
        # Lazily create for tests/TestClient without lifespan.
        from compassx.container import PlatformContainer

        platform = PlatformContainer()
        request.app.state.platform = platform
    return platform


def get_service_registry(request: Request):
    """Deployment-independent service endpoint resolution."""
    return get_platform(request).service_registry


def get_monitoring_resource_manager(request: Request):
    """Profile-aware source of observed platform resource metrics."""
    return get_platform(request).monitoring_resource_manager


def get_runtime_manager(request: Request):
    """RuntimeManager backed by the SQL runtime repository."""
    manager = getattr(request.app.state, "runtime_manager", None)
    if manager is None:
        from app.database import SystemSessionLocal
        from compassx.runtime.repository import SqlRuntimeRepository

        repository = None
        if SystemSessionLocal is not None:
            repository = SqlRuntimeRepository(SystemSessionLocal)
        manager = get_platform(request).build_runtime_manager(repository)
        request.app.state.runtime_manager = manager
    return manager
