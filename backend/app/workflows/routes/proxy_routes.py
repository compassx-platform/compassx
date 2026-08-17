"""Proxy routes – forward requests to Asset Manager with authkey."""

from __future__ import annotations

from fastapi import APIRouter, Request, Header
import httpx

from app.config import settings

router = APIRouter(prefix="/api/v1/proxy", tags=["Proxy"])

AM_BASE = settings.ASSET_MANAGER_BASE_URL


@router.get("/asset-types")
async def proxy_asset_types(request: Request, authkey: str = Header(...)):
    """Proxy GET /asset-types to Asset Manager."""
    url = f"{AM_BASE}/asset-manager/api/v1/asset-types"
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers={"authkey": authkey})
    return resp.json()


@router.get("/assets")
async def proxy_assets(request: Request, authkey: str = Header(...)):
    """Proxy GET /assets to Asset Manager."""
    url = f"{AM_BASE}/asset-manager/api/v1/assets"
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers={"authkey": authkey})
    return resp.json()


@router.post("/child-assets")
async def proxy_child_assets(request: Request, authkey: str = Header(...)):
    """Proxy POST /child-assets to Asset Manager."""
    url = f"{AM_BASE}/asset-manager/api/v1/child-assets"
    body = await request.json()
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=body, params=params, headers={"authkey": authkey})
    return resp.json()


@router.post("/child-asset-types")
async def proxy_child_asset_types(request: Request, authkey: str = Header(...)):
    """Proxy POST /child-asset-types to Asset Manager."""
    url = f"{AM_BASE}/asset-manager/api/v1/child-asset-types"
    body = await request.json()
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=body, params=params, headers={"authkey": authkey})
    return resp.json()


@router.get("/asset-types-hierarchies")
async def proxy_asset_type_hierarchies(request: Request, authkey: str = Header(...)):
    """Proxy GET /asset-types-hierarchies to Asset Manager."""
    url = f"{AM_BASE}/asset-manager/api/v1/asset-types-hierarchies"
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers={"authkey": authkey})
    return resp.json()
