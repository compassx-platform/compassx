"""Asset enrichment service – resolves asset_id → asset_name via Asset Manager API."""

from __future__ import annotations

from functools import lru_cache

import httpx

from app.config import settings

# Simple in-memory cache (per process) – short-lived since LRU has 256 entries max.
_cache: dict[str, str] = {}


async def enrich_asset_names(
    asset_ids: list[str],
    authkey: str,
) -> dict[str, str]:
    """Batch-resolve asset IDs to names.

    Returns { "asset_id_str": "Asset Name" }.
    """
    result: dict[str, str] = {}
    to_fetch: list[str] = []

    for aid in asset_ids:
        if aid in _cache:
            result[aid] = _cache[aid]
        else:
            to_fetch.append(aid)

    if not to_fetch:
        return result

    # Fetch from Asset Manager in batch (using the GET /assets?id=... endpoint)
    url = f"{settings.ASSET_MANAGER_BASE_URL}/asset-manager/api/v1/assets"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for aid in to_fetch:
                resp = await client.get(
                    url,
                    params={"id": aid},
                    headers={"authkey": authkey},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    items = body.get("items", [])
                    if items:
                        name = items[0].get("name", f"Asset {aid}")
                        result[aid] = name
                        _cache[aid] = name
                    else:
                        result[aid] = f"Unknown Asset ({aid})"
                else:
                    result[aid] = f"Unknown Asset ({aid})"
    except httpx.RequestError:
        # If Asset Manager is unreachable, return IDs as names
        for aid in to_fetch:
            result[aid] = f"Asset {aid}"

    return result


def clear_cache():
    """Clear the enrichment cache (useful for testing)."""
    _cache.clear()
