from __future__ import annotations

def _bind():
    import services.enterprise_gateway.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def list_kernelspecs():
    """List available kernelspecs for UI dropdown."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{_eg_base_url()}/api/kernelspecs")
            if resp.status_code != 200:
                return _error("EGError", "Could not fetch kernelspecs.", resp.status_code)
            return resp.json()
    except Exception as exc:
        logger.warning("EG kernelspecs failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)
