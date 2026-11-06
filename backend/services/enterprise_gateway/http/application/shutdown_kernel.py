from __future__ import annotations

def _bind():
    import services.enterprise_gateway.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def shutdown_kernel(kernel_id: str):
    """Shutdown a kernel."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.delete(f"{_eg_base_url()}/api/kernels/{kernel_id}")
            if resp.status_code == 404:
                return _error("NotFound", f"Kernel {kernel_id} not found.", 404)
            return {"shutdown": True, "kernel_id": kernel_id}
    except Exception as exc:
        logger.warning("EG kernel shutdown failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)
