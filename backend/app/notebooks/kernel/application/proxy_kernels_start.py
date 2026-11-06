import json

import httpx
from fastapi import Request
from fastapi.responses import Response

from app.notebooks.kernel.registry import (
    _HOP_BY_HOP,
    _authorize_resource,
    _eg_http_url,
    _kernel_catalog_api_url,
)


class ProxyKernelsStart:
    async def execute(self, request: Request, guard, db):
        body = await request.body()
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        # A kernel is a pod running the caller's code, so starting one takes the
        # same USE_COMPUTE that /compute/resources/{id}/start-kernel takes. The
        # resource comes from the request, so it is checked rather than trusted.
        env = payload.get("env") or {}
        _authorize_resource(guard, db, env.get("KERNEL_COMPASSX_JOB_ID"))

        auth_header = request.headers.get("Authorization", "")
        session_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

        if "env" not in payload:
            payload["env"] = {}

        ws_id_str = ""
        ws_slug_str = ""
        if hasattr(request.state, "workspace") and request.state.workspace:
            ws_id_str = str(getattr(request.state.workspace, "workspace_id", "") or "")
            ws_slug_str = str(getattr(request.state.workspace, "workspace_slug", "") or "")
        elif request.query_params.get("workspace"):
            ws_slug_str = request.query_params.get("workspace") or ""
        elif request.headers.get("x-workspace-slug"):
            ws_slug_str = request.headers.get("x-workspace-slug") or ""

        if ws_slug_str and not ws_id_str:
            try:
                from app.workspace.models import Workspace
                ws_obj = db.query(Workspace).filter((Workspace.slug == ws_slug_str) | (Workspace.id == ws_slug_str)).first()
                if ws_obj:
                    ws_id_str = str(ws_obj.id)
                    ws_slug_str = ws_obj.slug
            except Exception:
                pass

        catalog_api_url = _kernel_catalog_api_url()
        payload["env"].setdefault("KERNEL_NOTEBOOK_SESSION_TOKEN", session_token)
        payload["env"].setdefault("KERNEL_CATALOG_API_URL", catalog_api_url)
        payload["env"].setdefault("NOTEBOOK_SESSION_TOKEN", session_token)
        payload["env"].setdefault("CATALOG_API_URL", catalog_api_url)
        if ws_id_str:
            payload["env"].setdefault("KERNEL_WORKSPACE_ID", ws_id_str)
            payload["env"].setdefault("WORKSPACE_ID", ws_id_str)
        if ws_slug_str:
            payload["env"].setdefault("KERNEL_WORKSPACE_SLUG", ws_slug_str)
            payload["env"].setdefault("WORKSPACE_SLUG", ws_slug_str)

        # Ambient MLflow Tracking & Storage credentials injection
        try:
            from compassx.lookup import try_resolve_url_container
            mlflow_url = try_resolve_url_container("mlflow", "http://mlflow:5000")
            minio_url = try_resolve_url_container("minio", "http://minio:9000")
        except Exception:
            mlflow_url = "http://mlflow:5000"
            minio_url = "http://minio:9000"

        storage_key = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
        storage_secret = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
        storage_region = os.environ.get("STORAGE_REGION", "us-east-1")

        payload["env"].setdefault("MLFLOW_TRACKING_URI", mlflow_url)
        payload["env"].setdefault("KERNEL_MLFLOW_TRACKING_URI", mlflow_url)
        payload["env"].setdefault("MLFLOW_S3_ENDPOINT_URL", minio_url)
        payload["env"].setdefault("KERNEL_MLFLOW_S3_ENDPOINT_URL", minio_url)
        payload["env"].setdefault("AWS_ACCESS_KEY_ID", storage_key)
        payload["env"].setdefault("KERNEL_AWS_ACCESS_KEY_ID", storage_key)
        payload["env"].setdefault("AWS_SECRET_ACCESS_KEY", storage_secret)
        payload["env"].setdefault("KERNEL_AWS_SECRET_ACCESS_KEY", storage_secret)
        payload["env"].setdefault("AWS_DEFAULT_REGION", storage_region)
        payload["env"].setdefault("KERNEL_AWS_DEFAULT_REGION", storage_region)

        modified_body = json.dumps(payload).encode("utf-8")

        # Forward to upstream EG
        base = _eg_http_url()
        target_url = f"{base}/api/kernels"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        forward_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            upstream = await client.request("POST", target_url, headers=forward_headers, content=modified_body)

        response_headers = {
            k: v for k, v in upstream.headers.items()
            if k.lower() not in _HOP_BY_HOP
            and k.lower() not in ("content-encoding", "content-length")
        }
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=upstream.headers.get("content-type"),
        )


def proxy_kernels_start(request, guard, db):
    return ProxyKernelsStart().execute(request, guard, db)
