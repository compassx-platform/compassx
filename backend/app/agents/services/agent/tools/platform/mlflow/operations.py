from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.database import AccountSessionLocal
from app.catalog.models import UnifiedCatalogConnection
from app.catalog.connections.service import connection_service
from app.models.agents import Agent

logger = logging.getLogger(__name__)

MLFLOW_OPERATIONS = [
    # Experiments
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "update_experiment",
    "delete_experiment",
    # Runs
    "create_run",
    "get_run",
    "search_runs",
    "update_run",
    "delete_run",
    "log_param",
    "log_metric",
    "log_batch",
    "set_tag",
    "log_model",
    "list_artifacts",
    # Model registry
    "register_model",
    "list_registered_models",
    "get_registered_model",
    "update_registered_model",
    "delete_registered_model",
    "create_model_version",
    "get_model_version",
    "update_model_version",
    "delete_model_version",
    "search_model_versions",
    "transition_model_version_stage",
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "get_model_version_by_alias",
]

_TIMEOUT_SECONDS = 30.0


class MlflowApiError(Exception):
    """A non-2xx response from the MLflow tracking server."""


class _MlflowRestClient:
    """Thin synchronous REST client for the MLflow tracking API.

    Auth is resolved per-call from a decrypted Catalog Connection and sent
    as an explicit header on each request, rather than through MLflow's own
    client library (which authenticates via process-wide environment
    variables — unsafe here since one backend process serves concurrent
    calls against connections for different workspaces/credentials).
    """

    def __init__(self, base_url: str, auth_config: Any) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {}
        self._basic_auth: tuple[str, str] | None = None

        cfg = auth_config if isinstance(auth_config, dict) else {}
        token = cfg.get("token") or cfg.get("bearer_token") or cfg.get("api_key")
        username = cfg.get("username")
        password = cfg.get("password")
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self._basic_auth = (username, password)
        extra_headers = cfg.get("headers")
        if isinstance(extra_headers, dict):
            self._headers.update({str(k): str(v) for k, v in extra_headers.items()})

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        clean_body = {k: v for k, v in (json_body or {}).items() if v is not None} if json_body is not None else None
        try:
            resp = httpx.request(
                method,
                url,
                params=clean_params or None,
                json=clean_body,
                headers=self._headers or None,
                auth=self._basic_auth,
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise MlflowApiError(f"Could not reach MLflow server at {self._base_url}: {exc}") from exc

        if resp.status_code >= 400:
            try:
                detail = resp.json()
                message = detail.get("message") or detail.get("error_code") or resp.text
            except Exception:
                message = resp.text
            raise MlflowApiError(f"MLflow API error ({resp.status_code}) on {method} {path}: {message}")

        if not resp.content:
            return {}
        return resp.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, json_body=body or {})

    def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("PATCH", path, json_body=body or {})

    def delete(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("DELETE", path, json_body=body or {})


def _resolve_connection(
    account_db: Session,
    payload: dict[str, Any],
) -> tuple[UnifiedCatalogConnection | None, str | None]:
    """Find the MLflow ``UnifiedCatalogConnection`` to use for this call.

    This is the same first-class Catalog Connection store used by the
    Connections page (``app.catalog.connections``) — not workspace-scoped.
    An explicit ``connection_id`` or ``connection_name`` in the payload wins;
    otherwise, if there is exactly one active ``mlflow`` connection, use it.
    Ambiguous or missing cases return a clear error listing what exists,
    mirroring the SQL Warehouse tool's warehouse resolution.
    """
    connection_id = payload.get("connection_id")
    connection_name = payload.get("connection_name") or payload.get("connection")

    if connection_id or connection_name:
        conn = connection_service.get_connection(account_db, str(connection_id or connection_name))
        if not conn or conn.connector_type != "mlflow" or conn.status != "active":
            return None, f"MLflow connection '{connection_id or connection_name}' not found or inactive."
        return conn, None

    candidates = connection_service.list_connections(account_db, connector_type="mlflow", status="active")
    if not candidates:
        return None, (
            "No active MLflow connection configured. Create one under Connections "
            "with connector type 'MLflow' first."
        )
    if len(candidates) > 1:
        names = [f"{c.name} ({c.id})" for c in candidates]
        return None, (
            f"Multiple MLflow connections found; specify 'connection_id' or 'connection_name'. "
            f"Available: {names}"
        )
    return candidates[0], None


def _client_for(payload: dict[str, Any], context: dict[str, Any] | None, agent: Agent | None) -> tuple[_MlflowRestClient | None, str | None]:
    account_db = AccountSessionLocal()
    try:
        conn, err = _resolve_connection(account_db, payload)
        if err:
            return None, err
        auth_config = connection_service.get_decrypted_auth_config(conn)
        return _MlflowRestClient(conn.config.get("base_url", ""), auth_config), None
    finally:
        account_db.close()


# ── Experiments ──────────────────────────────────────────────────────────────

def create_experiment(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    if not name:
        return {"ok": False, "error": "Missing required parameter 'name'"}
    body = {
        "name": name,
        "artifact_location": payload.get("artifact_location"),
        "tags": payload.get("tags"),
    }
    data = client.post("/api/2.0/mlflow/experiments/create", body)
    return {"ok": True, "experiment_id": data.get("experiment_id")}


def get_experiment(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    experiment_id = payload.get("experiment_id")
    experiment_name = payload.get("experiment_name") or payload.get("name")
    if experiment_id:
        data = client.get("/api/2.0/mlflow/experiments/get", {"experiment_id": experiment_id})
    elif experiment_name:
        data = client.get("/api/2.0/mlflow/experiments/get-by-name", {"experiment_name": experiment_name})
    else:
        return {"ok": False, "error": "Provide 'experiment_id' or 'experiment_name'"}
    return {"ok": True, "experiment": data.get("experiment")}


def list_experiments(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    body = {
        "max_results": payload.get("max_results", 1000),
        "page_token": payload.get("page_token"),
        "filter": payload.get("filter"),
        "order_by": payload.get("order_by"),
        "view_type": payload.get("view_type"),
    }
    data = client.post("/api/2.0/mlflow/experiments/search", body)
    return {"ok": True, "experiments": data.get("experiments", []), "next_page_token": data.get("next_page_token")}


def update_experiment(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    experiment_id = payload.get("experiment_id")
    if not experiment_id:
        return {"ok": False, "error": "Missing required parameter 'experiment_id'"}
    body = {"experiment_id": experiment_id, "new_name": payload.get("new_name")}
    client.post("/api/2.0/mlflow/experiments/update", body)
    return {"ok": True, "experiment_id": experiment_id}


def delete_experiment(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    experiment_id = payload.get("experiment_id")
    if not experiment_id:
        return {"ok": False, "error": "Missing required parameter 'experiment_id'"}
    client.post("/api/2.0/mlflow/experiments/delete", {"experiment_id": experiment_id})
    return {"ok": True, "experiment_id": experiment_id}


# ── Runs ─────────────────────────────────────────────────────────────────────

def create_run(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    experiment_id = payload.get("experiment_id")
    if not experiment_id:
        return {"ok": False, "error": "Missing required parameter 'experiment_id'"}
    body = {
        "experiment_id": experiment_id,
        "start_time": payload.get("start_time"),
        "run_name": payload.get("run_name"),
        "tags": payload.get("tags"),
    }
    data = client.post("/api/2.0/mlflow/runs/create", body)
    run = data.get("run", {})
    return {"ok": True, "run": run, "run_id": run.get("info", {}).get("run_id")}


def get_run(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        return {"ok": False, "error": "Missing required parameter 'run_id'"}
    data = client.get("/api/2.0/mlflow/runs/get", {"run_id": run_id})
    return {"ok": True, "run": data.get("run")}


def search_runs(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    experiment_ids = payload.get("experiment_ids")
    if not experiment_ids:
        experiment_id = payload.get("experiment_id")
        experiment_ids = [experiment_id] if experiment_id else None
    if not experiment_ids:
        return {"ok": False, "error": "Provide 'experiment_ids' (list) or 'experiment_id'"}
    body = {
        "experiment_ids": experiment_ids,
        "filter": payload.get("filter"),
        "run_view_type": payload.get("run_view_type", "ACTIVE_ONLY"),
        "max_results": payload.get("max_results", 1000),
        "order_by": payload.get("order_by"),
        "page_token": payload.get("page_token"),
    }
    data = client.post("/api/2.0/mlflow/runs/search", body)
    return {"ok": True, "runs": data.get("runs", []), "next_page_token": data.get("next_page_token")}


def update_run(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        return {"ok": False, "error": "Missing required parameter 'run_id'"}
    body = {
        "run_id": run_id,
        "status": payload.get("status"),
        "end_time": payload.get("end_time"),
        "run_name": payload.get("run_name"),
    }
    data = client.post("/api/2.0/mlflow/runs/update", body)
    return {"ok": True, "run_info": data.get("run_info")}


def delete_run(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        return {"ok": False, "error": "Missing required parameter 'run_id'"}
    client.post("/api/2.0/mlflow/runs/delete", {"run_id": run_id})
    return {"ok": True, "run_id": run_id}


def log_param(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id, key = payload.get("run_id"), payload.get("key")
    if not run_id or key is None:
        return {"ok": False, "error": "Missing required parameters 'run_id' and 'key'"}
    client.post("/api/2.0/mlflow/runs/log-parameter", {"run_id": run_id, "key": key, "value": str(payload.get("value", ""))})
    return {"ok": True}


def log_metric(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id, key = payload.get("run_id"), payload.get("key")
    if not run_id or key is None or "value" not in payload:
        return {"ok": False, "error": "Missing required parameters 'run_id', 'key', 'value'"}
    body = {
        "run_id": run_id,
        "key": key,
        "value": float(payload["value"]),
        "timestamp": payload.get("timestamp") or _now_ms(),
        "step": payload.get("step", 0),
    }
    client.post("/api/2.0/mlflow/runs/log-metric", body)
    return {"ok": True}


def log_batch(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        return {"ok": False, "error": "Missing required parameter 'run_id'"}
    now = _now_ms()
    metrics = [
        {"key": m["key"], "value": float(m["value"]), "timestamp": m.get("timestamp") or now, "step": m.get("step", 0)}
        for m in payload.get("metrics", [])
    ]
    params = [{"key": p["key"], "value": str(p["value"])} for p in payload.get("params", [])]
    tags = [{"key": t["key"], "value": str(t["value"])} for t in payload.get("tags", [])]
    body = {"run_id": run_id, "metrics": metrics or None, "params": params or None, "tags": tags or None}
    client.post("/api/2.0/mlflow/runs/log-batch", body)
    return {"ok": True, "logged": {"metrics": len(metrics), "params": len(params), "tags": len(tags)}}


def set_tag(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id, key = payload.get("run_id"), payload.get("key")
    if not run_id or key is None:
        return {"ok": False, "error": "Missing required parameters 'run_id' and 'key'"}
    client.post("/api/2.0/mlflow/runs/set-tag", {"run_id": run_id, "key": key, "value": str(payload.get("value", ""))})
    return {"ok": True}


def list_artifacts(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        return {"ok": False, "error": "Missing required parameter 'run_id'"}
    data = client.get("/api/2.0/mlflow/artifacts/list", {"run_id": run_id, "path": payload.get("path")})
    return {"ok": True, "files": data.get("files", []), "root_uri": data.get("root_uri")}


def log_model(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    """Log a model reference by writing the MLmodel-style logged-model tag on a run.

    This records model metadata (name, flavor, source artifact path already
    uploaded under the run) against the run, then optionally registers it — it
    does not itself serialize/upload a Python model object, since a tool
    invoked over JSON args can't carry one. Upload the model artifact first
    (e.g. via a notebook/code tool saving into the run's artifact path), then
    call this with 'artifact_path' pointing at it.
    """
    run_id = payload.get("run_id")
    artifact_path = payload.get("artifact_path")
    if not run_id or not artifact_path:
        return {"ok": False, "error": "Missing required parameters 'run_id' and 'artifact_path'"}
    flavor = payload.get("flavor", "pyfunc")
    tag_value = {
        "artifact_path": artifact_path,
        "flavor": flavor,
        "utc_time_created": payload.get("utc_time_created"),
        "run_id": run_id,
    }
    import json as _json

    client.post("/api/2.0/mlflow/runs/set-tag", {"run_id": run_id, "key": f"mlflow.log-model.history.{artifact_path}", "value": _json.dumps(tag_value)})

    result: dict[str, Any] = {"ok": True, "run_id": run_id, "artifact_path": artifact_path}
    registered_name = payload.get("registered_model_name")
    if registered_name:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        reg = register_model(client, {"name": registered_name, "source": model_uri, "run_id": run_id})
        result["registered_model"] = reg
    return result


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


# ── Model registry ───────────────────────────────────────────────────────────

def register_model(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    if not name:
        return {"ok": False, "error": "Missing required parameter 'name'"}
    # Ensure the registered model exists (idempotent create).
    try:
        client.post("/api/2.0/mlflow/registered-models/create", {"name": name, "description": payload.get("description")})
    except MlflowApiError as exc:
        if "already exists" not in str(exc).lower() and "RESOURCE_ALREADY_EXISTS" not in str(exc):
            raise
    source = payload.get("source")
    run_id = payload.get("run_id")
    if not source:
        return {"ok": True, "name": name, "message": "Registered model ensured; no 'source' given so no version was created."}
    body = {"name": name, "source": source, "run_id": run_id, "tags": payload.get("tags"), "run_link": payload.get("run_link")}
    data = client.post("/api/2.0/mlflow/model-versions/create", body)
    return {"ok": True, "model_version": data.get("model_version")}


def list_registered_models(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    params = {
        "max_results": payload.get("max_results", 1000),
        "filter": payload.get("filter"),
        "order_by": payload.get("order_by"),
        "page_token": payload.get("page_token"),
    }
    data = client.get("/api/2.0/mlflow/registered-models/search", params)
    return {"ok": True, "registered_models": data.get("registered_models", []), "next_page_token": data.get("next_page_token")}


def get_registered_model(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    if not name:
        return {"ok": False, "error": "Missing required parameter 'name'"}
    data = client.get("/api/2.0/mlflow/registered-models/get", {"name": name})
    return {"ok": True, "registered_model": data.get("registered_model")}


def update_registered_model(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    if not name:
        return {"ok": False, "error": "Missing required parameter 'name'"}
    new_name = payload.get("new_name")
    if new_name:
        client.post("/api/2.0/mlflow/registered-models/rename", {"name": name, "new_name": new_name})
        name = new_name
    if payload.get("description") is not None:
        client.patch("/api/2.0/mlflow/registered-models/update", {"name": name, "description": payload.get("description")})
    return {"ok": True, "name": name}


def delete_registered_model(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    if not name:
        return {"ok": False, "error": "Missing required parameter 'name'"}
    client.delete("/api/2.0/mlflow/registered-models/delete", {"name": name})
    return {"ok": True, "name": name}


def create_model_version(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, source = payload.get("name"), payload.get("source")
    if not name or not source:
        return {"ok": False, "error": "Missing required parameters 'name' and 'source'"}
    body = {"name": name, "source": source, "run_id": payload.get("run_id"), "tags": payload.get("tags"), "run_link": payload.get("run_link")}
    data = client.post("/api/2.0/mlflow/model-versions/create", body)
    return {"ok": True, "model_version": data.get("model_version")}


def get_model_version(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, version = payload.get("name"), payload.get("version")
    if not name or not version:
        return {"ok": False, "error": "Missing required parameters 'name' and 'version'"}
    data = client.get("/api/2.0/mlflow/model-versions/get", {"name": name, "version": version})
    return {"ok": True, "model_version": data.get("model_version")}


def update_model_version(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, version = payload.get("name"), payload.get("version")
    if not name or not version:
        return {"ok": False, "error": "Missing required parameters 'name' and 'version'"}
    client.patch("/api/2.0/mlflow/model-versions/update", {"name": name, "version": version, "description": payload.get("description")})
    return {"ok": True, "name": name, "version": version}


def delete_model_version(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, version = payload.get("name"), payload.get("version")
    if not name or not version:
        return {"ok": False, "error": "Missing required parameters 'name' and 'version'"}
    client.delete("/api/2.0/mlflow/model-versions/delete", {"name": name, "version": version})
    return {"ok": True, "name": name, "version": version}


def search_model_versions(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    params = {
        "filter": payload.get("filter"),
        "max_results": payload.get("max_results", 1000),
        "order_by": payload.get("order_by"),
        "page_token": payload.get("page_token"),
    }
    data = client.get("/api/2.0/mlflow/model-versions/search", params)
    return {"ok": True, "model_versions": data.get("model_versions", []), "next_page_token": data.get("next_page_token")}


def transition_model_version_stage(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, version, stage = payload.get("name"), payload.get("version"), payload.get("stage")
    if not name or not version or not stage:
        return {"ok": False, "error": "Missing required parameters 'name', 'version', 'stage'"}
    body = {
        "name": name,
        "version": version,
        "stage": stage,
        "archive_existing_versions": bool(payload.get("archive_existing_versions", False)),
    }
    data = client.post("/api/2.0/mlflow/model-versions/transition-stage", body)
    return {"ok": True, "model_version": data.get("model_version")}


def set_registered_model_alias(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, alias, version = payload.get("name"), payload.get("alias"), payload.get("version")
    if not name or not alias or not version:
        return {"ok": False, "error": "Missing required parameters 'name', 'alias', 'version'"}
    client.post("/api/2.0/mlflow/registered-models/alias", {"name": name, "alias": alias, "version": version})
    return {"ok": True, "name": name, "alias": alias, "version": version}


def delete_registered_model_alias(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, alias = payload.get("name"), payload.get("alias")
    if not name or not alias:
        return {"ok": False, "error": "Missing required parameters 'name' and 'alias'"}
    client.delete("/api/2.0/mlflow/registered-models/alias", {"name": name, "alias": alias})
    return {"ok": True, "name": name, "alias": alias}


def get_model_version_by_alias(client: _MlflowRestClient, payload: dict[str, Any]) -> dict[str, Any]:
    name, alias = payload.get("name"), payload.get("alias")
    if not name or not alias:
        return {"ok": False, "error": "Missing required parameters 'name' and 'alias'"}
    data = client.get("/api/2.0/mlflow/registered-models/alias", {"name": name, "alias": alias})
    return {"ok": True, "model_version": data.get("model_version")}


_OPERATION_HANDLERS = {
    "create_experiment": create_experiment,
    "get_experiment": get_experiment,
    "list_experiments": list_experiments,
    "update_experiment": update_experiment,
    "delete_experiment": delete_experiment,
    "create_run": create_run,
    "get_run": get_run,
    "search_runs": search_runs,
    "update_run": update_run,
    "delete_run": delete_run,
    "log_param": log_param,
    "log_metric": log_metric,
    "log_batch": log_batch,
    "set_tag": set_tag,
    "log_model": log_model,
    "list_artifacts": list_artifacts,
    "register_model": register_model,
    "list_registered_models": list_registered_models,
    "get_registered_model": get_registered_model,
    "update_registered_model": update_registered_model,
    "delete_registered_model": delete_registered_model,
    "create_model_version": create_model_version,
    "get_model_version": get_model_version,
    "update_model_version": update_model_version,
    "delete_model_version": delete_model_version,
    "search_model_versions": search_model_versions,
    "transition_model_version_stage": transition_model_version_stage,
    "set_registered_model_alias": set_registered_model_alias,
    "delete_registered_model_alias": delete_registered_model_alias,
    "get_model_version_by_alias": get_model_version_by_alias,
}


def execute_mlflow_operation(
    operation: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Dispatch an MLflow operation against the resolved connection."""
    op = (operation or "").strip()
    handler = _OPERATION_HANDLERS.get(op)
    if handler is None:
        raise ValueError(f"Unsupported mlflow operation: {operation!r}. Supported operations: {MLFLOW_OPERATIONS}")

    client, err = _client_for(payload, context, agent)
    if err:
        return {"ok": False, "error": err}

    try:
        return handler(client, payload)
    except MlflowApiError as exc:
        logger.warning("MLflow operation %s failed: %s", op, exc)
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("MLflow operation %s raised unexpectedly: %s", op, exc)
        return {"ok": False, "error": f"MLflow operation failed: {exc}"}
