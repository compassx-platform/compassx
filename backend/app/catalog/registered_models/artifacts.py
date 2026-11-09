"""Copy MLflow run artifacts into catalog storage."""
from __future__ import annotations

import os
from typing import Any

import httpx
from compassx.lookup import try_resolve_url

_MAX_FILES = 50
_MAX_BYTES = 200 * 1024 * 1024


class RegistryError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def safe_artifact_relative(path: str) -> str:
    """Reject absolute paths and parent segments in an artifact path."""
    cleaned = str(path or "").replace("\\", "/").strip().strip("/")
    if not cleaned:
        return ""
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise RegistryError(400, "Artifact path cannot contain '..' or be absolute.")
    return "/".join(parts)


def storage_relative(model_name: str, version: int, artifact_relative: str) -> str:
    relative = safe_artifact_relative(artifact_relative)
    suffix = f"/{relative}" if relative else ""
    return f"models/{model_name}/versions/{version}{suffix}"


def _pairs(items: list[dict] | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in items or []:
        if isinstance(item, dict) and item.get("key") is not None:
            values[str(item["key"])] = item.get("value")
    return values


def tracking_url() -> str:
    return try_resolve_url("mlflow", os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5555")).rstrip("/")


async def load_run(client: httpx.AsyncClient, run_id: str) -> dict[str, Any]:
    response = await client.get(f"{tracking_url()}/api/2.0/mlflow/runs/get", params={"run_id": run_id})
    if response.status_code == 404:
        raise RegistryError(404, f"MLflow run '{run_id}' was not found.")
    if response.status_code >= 400:
        raise RegistryError(502, f"MLflow could not load run '{run_id}'.")
    run = (response.json() or {}).get("run") or {}
    data = run.get("data") or {}
    info = run.get("info") or {}
    return {
        "run_id": run_id,
        "status": info.get("status"),
        "metrics": _pairs(data.get("metrics")),
        "params": _pairs(data.get("params")),
    }


async def _list_files(client: httpx.AsyncClient, run_id: str, path: str) -> list[dict]:
    response = await client.get(
        f"{tracking_url()}/api/2.0/mlflow/artifacts/list",
        params={"run_id": run_id, "path": path},
    )
    if response.status_code >= 400:
        raise RegistryError(502, f"MLflow could not list artifacts at '{path or '/'}'.")
    return list((response.json() or {}).get("files") or [])


async def artifact_paths(client: httpx.AsyncClient, run_id: str, artifact_path: str) -> list[str]:
    """Files to copy. An empty path copies the whole run; a file path copies that file."""
    requested = safe_artifact_relative(artifact_path)
    listed = await _list_files(client, run_id, requested)
    files: list[str] = []

    async def walk(entries: list[dict]) -> None:
        for entry in entries:
            entry_path = str(entry.get("path") or "")
            if not entry_path:
                continue
            if entry.get("is_dir"):
                await walk(await _list_files(client, run_id, entry_path))
            else:
                files.append(safe_artifact_relative(entry_path))
                if len(files) > _MAX_FILES:
                    raise RegistryError(400, f"A model version can contain at most {_MAX_FILES} files.")

    if listed:
        await walk(listed)
    elif requested:
        files.append(requested)
    if not files:
        raise RegistryError(404, "This run has no artifacts to register.")
    return files


async def download_artifact(client: httpx.AsyncClient, run_id: str, path: str) -> bytes:
    base = tracking_url()
    last_status = 0
    for params in ({"path": path, "run_uuid": run_id}, {"path": path, "run_id": run_id}):
        response = await client.get(f"{base}/get-artifact", params=params)
        last_status = response.status_code
        if response.status_code == 200 and response.content:
            if len(response.content) > _MAX_BYTES:
                raise RegistryError(400, f"Artifact '{path}' is larger than 200 MB.")
            return response.content
    raise RegistryError(404, f"Artifact '{path}' was not found on the run (HTTP {last_status}).")
