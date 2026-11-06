"""Auth dependency. Identity comes from the workspace gate, never from a fixed user."""

from fastapi import HTTPException, Request, status


async def get_current_user(
    request: Request,
) -> dict:
    """Return the caller the workspace middleware already authenticated."""
    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return {
        "id": str(ctx.principal_id),
        "sub": str(ctx.principal_id),
        "email": "",
        "org_id": "",
        "name": "",
        "is_account_admin": bool(ctx.is_account_admin),
        "workspace_id": str(ctx.workspace_id),
        "workspace_role": ctx.principal_role,
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
