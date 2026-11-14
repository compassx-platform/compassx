from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

async def sandbox_platform_tool(request: Request):
    """Execute a CompassX platform tool on behalf of Nova running in a sandbox."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    from app.agent_runtime.sandbox_tools import execute_platform_tool

    try:
        return await execute_platform_tool(request, body if isinstance(body, dict) else {})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:400])
