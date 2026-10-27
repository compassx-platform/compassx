"""
Notebook routes (prefix: /api/v1/notebook):
  GET  /api/v1/notebook/config           — jupyter_server connection settings
  GET  /api/v1/notebook/list             — list .ipynb files in notebooks bucket
  POST /api/v1/notebook/create           — create a new .ipynb file
  DELETE /api/v1/notebook/files/{path}   — delete a .ipynb file
  GET  /api/v1/notebook/files/{path}     — load .ipynb content
  PUT  /api/v1/notebook/files/{path}     — save .ipynb content
"""
import json
import logging
import os

from sqlalchemy.exc import SQLAlchemyError

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_account_db
from app.dependencies import get_current_user
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable

from compute.config import compute_settings
from services.storage.config import storage_settings
from services.storage.fs import get_fs

router = APIRouter(prefix="/api/v1/notebook", tags=["notebook"])
logger = logging.getLogger(__name__)

JUPYTER_TOKEN = os.environ.get("JUPYTER_TOKEN", "")

# In local dev the Vite proxy handles /api/kernels → EG (8888) directly, so
# the frontend can use localhost:5173 as its Jupyter base URL.
 # In K8s, compassx-jupyter-server is exposed via LoadBalancer, so we
# route all Jupyter REST + WebSocket traffic through the backend proxy.
# In deployed environments, route Jupyter traffic through the backend proxy.
_JUPYTER_PROXY_PATH = "/api/v1/notebook/jupyter"

def _jupyter_base_url() -> str:
    if os.environ.get("JUPYTER_BASE_URL"):
        return os.environ["JUPYTER_BASE_URL"].rstrip("/")
    return _JUPYTER_PROXY_PATH

def _jupyter_ws_url() -> str:
    if os.environ.get("JUPYTER_WS_URL"):
        return os.environ["JUPYTER_WS_URL"].rstrip("/")
    # Frontend converts http→ws based on window.location; return same path.
    return _JUPYTER_PROXY_PATH

_NOTEBOOKS_PREFIX = storage_settings.STORAGE_NOTEBOOKS_PREFIX.strip("/")
_NOTEBOOKS_BUCKET = storage_settings.STORAGE_NOTEBOOKS_BUCKET


def _safe_key(path: str) -> str:
    """Convert a relative notebook path to a storage key; reject path traversal."""
    # Normalise separators and strip leading slashes
    clean = path.replace("\\", "/").lstrip("/")
    # Reject traversal attempts
    if ".." in clean.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    prefix = _NOTEBOOKS_PREFIX
    return f"{prefix}/{clean}" if prefix else clean


def _key_to_rel(key: str) -> str:
    """Strip the notebooks prefix from a storage key to get the relative path."""
    prefix = _NOTEBOOKS_PREFIX
    if prefix and key.startswith(f"{prefix}/"):
        return key[len(prefix) + 1 :]
    return key


def _catalog_storage_location(db: Session, notebook, workspace_id: str | None = None) -> str:
    from app.catalog.storage_context import resolve_catalog_storage_by_schema_id

    ctx = resolve_catalog_storage_by_schema_id(
        db,
        notebook.schema_id,
        workspace_id=workspace_id,
    )
    if ctx:
        return ctx.abs_path(f"notebooks/{notebook.blob_path}")
    return _safe_key(notebook.blob_path)


# ── Config ──────────────────────────────────────────────────────────────────

class NotebookServerConfig(BaseModel):
    base_url: str
    ws_url: str
    token: str
    workspace_slug: str


@router.get("/config", response_model=NotebookServerConfig)
def get_notebook_config(request: Request, guard: Guard = Depends(get_guard)):
    """Return jupyter connection settings for the frontend.

    ``token`` is deliberately empty. It used to be the deployment-wide
    ``JUPYTER_TOKEN``, which every user received identically — so it named
    nobody and could not be the basis of any decision, while still being
    enough to reach Enterprise Gateway. The frontend now appends the signed-in
    user's own access token, which is what the kernel proxy authenticates.

    ``workspace_slug`` is returned because a browser WebSocket cannot send the
    X-Workspace-Slug header the rest of the API relies on; it travels in the
    query string instead.
    """
    ctx = getattr(request.state, "workspace", None)
    return NotebookServerConfig(
        base_url=_jupyter_base_url(),
        ws_url=_jupyter_ws_url(),
        token="",
        workspace_slug=ctx.workspace_slug if ctx else "",
    )


# ── List / Create / Delete ───────────────────────────────────────────────────

@router.get("/list")
def list_notebooks(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List catalog notebooks visible in the active workspace."""
    from app.catalog.models import (
        CatalogWorkspaceBinding,
        UnifiedCatalogNotebook,
        UnifiedCatalogSchema,
    )

    query = db.query(UnifiedCatalogNotebook)
    workspace = getattr(request.state, "workspace", None)
    if workspace:
        catalog_ids = db.query(CatalogWorkspaceBinding.catalog_id).filter(
            CatalogWorkspaceBinding.workspace_id == workspace.workspace_id,
        )
        query = query.filter(
            UnifiedCatalogNotebook.schema.has(
                UnifiedCatalogSchema.catalog_id.in_(catalog_ids)
            )
        )
    records = query.order_by(
        UnifiedCatalogNotebook.catalog_name,
        UnifiedCatalogNotebook.schema_name,
        UnifiedCatalogNotebook.name,
    ).all()

    # The workspace binding above narrows this to catalogs bound to the
    # workspace, which is not the same as what this caller may see.
    records = guard.filter(
        Privilege.BROWSE,
        records,
        lambda n: Securable.notebook(n.catalog_name, n.schema_name, n.name),
    )
    workspace_id = workspace.workspace_id if workspace else None
    return {
        "notebooks": [
            {
                "id": notebook.id,
                "path": notebook.blob_path,
                "name": notebook.name,
                "full_name": notebook.full_name,
                "catalog_name": notebook.catalog_name,
                "schema_name": notebook.schema_name,
                "storage_location": _catalog_storage_location(db, notebook, workspace_id),
                "last_compute_resource_id": notebook.last_compute_resource_id,
                "last_kernel_name": notebook.last_kernel_name,
            }
            for notebook in records
        ]
    }


class NotebookComputeRequest(BaseModel):
    resource_id: str
    kernel_name: str


@router.put("/{notebook_id}/compute")
def save_notebook_compute(
    notebook_id: str,
    body: NotebookComputeRequest,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Save the last-connected compute resource and kernel name for a notebook."""
    from app.catalog.models import UnifiedCatalogNotebook

    notebook = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.id == notebook_id
    ).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")

    # This writes to the notebook record, so it takes EDIT — and it also
    # points the notebook at a compute resource, so the caller must be
    # entitled to run things there.
    guard.require(
        Privilege.EDIT,
        Securable.notebook(
            notebook.catalog_name, notebook.schema_name, notebook.name
        ),
    )
    guard.require(Privilege.USE_COMPUTE, Securable.compute(body.resource_id))

    notebook.last_compute_resource_id = body.resource_id
    notebook.last_kernel_name = body.kernel_name
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save compute info: {exc}") from exc
    return {"saved": True, "notebook_id": notebook_id}


class CreateRequest(BaseModel):
    name: str  # filename without extension, e.g. "my-analysis"
    folder: str = ""  # retained for request compatibility; catalog controls location
    catalog_name: str | None = None
    schema_name: str | None = None


@router.post("/create")
async def create_notebook(
    body: CreateRequest,
    request: Request,
    db: Session = Depends(get_account_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    """Create and register a notebook in catalog-resolved storage."""
    from app.catalog.models import (
        CatalogWorkspaceBinding,
        UnifiedCatalog,
        UnifiedCatalogSchema,
    )
    from app.catalog.schemas import NotebookCreate
    from app.catalog.service import create_notebook as create_catalog_notebook

    catalog_name = body.catalog_name
    schema_name = body.schema_name
    if not catalog_name or not schema_name:
        workspace = getattr(request.state, "workspace", None)
        if not workspace:
            raise HTTPException(
                status_code=422,
                detail="catalog_name and schema_name are required outside a workspace.",
            )
        binding = db.query(CatalogWorkspaceBinding).filter(
            CatalogWorkspaceBinding.workspace_id == workspace.workspace_id,
        ).order_by(CatalogWorkspaceBinding.is_default.desc()).first()
        catalog = db.query(UnifiedCatalog).filter(
            UnifiedCatalog.id == binding.catalog_id
        ).first() if binding else None
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id
        ).order_by(UnifiedCatalogSchema.name).first() if catalog else None
        if not catalog or not schema:
            raise HTTPException(
                status_code=422,
                detail="The workspace has no bound catalog schema for notebooks.",
            )
        catalog_name, schema_name = catalog.name, schema.name

    # Checked after the fallback above resolves a schema, because the caller
    # may not have named one — the workspace's default binding did.
    guard.require(Privilege.CREATE, Securable.schema_(catalog_name, schema_name))

    import re
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", body.name.strip()).strip("_") or "untitled"
    try:
        notebook = await create_catalog_notebook(
            db,
            catalog_name,
            schema_name,
            NotebookCreate(name=safe_name),
            user,
        )
    except ValueError as exc:
        status = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    guard.claim_ownership(
        Securable.notebook(catalog_name, schema_name, notebook.name)
    )
    return {
        "id": notebook.id,
        "path": notebook.blob_path,
        "name": notebook.name,
        "full_name": notebook.full_name,
        "catalog_name": notebook.catalog_name,
        "schema_name": notebook.schema_name,
        "storage_location": _catalog_storage_location(
            db,
            notebook,
            getattr(getattr(request.state, "workspace", None), "workspace_id", None),
        ),
    }


def _resolve_catalog_notebook(db, path: str):
    """Resolve a notebook path to a UnifiedCatalogNotebook record using multiple strategies.

    Supports:
      (a) exact blob_path:           <uuid>.ipynb
      (b) dot-separated FQN:         catalog.schema.name
      (c) slash-separated path:      catalog/schema/name.ipynb  (or without extension)
      (d) bare notebook name:        generate_scada_synthetic
    Returns None if no match is found or catalog metadata is unavailable.
    """
    from app.catalog.models import UnifiedCatalogNotebook

    try:
        # (a) exact blob_path
        notebook = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.blob_path == path
        ).first()
        if notebook:
            return notebook

        # (b) dot-separated FQN: catalog.schema.name  (must not end in .ipynb)
        dot_parts = path.split(".")
        if len(dot_parts) == 3 and not path.endswith(".ipynb"):
            notebook = db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == dot_parts[0],
                UnifiedCatalogNotebook.schema_name == dot_parts[1],
                UnifiedCatalogNotebook.name == dot_parts[2]
            ).first()
            if notebook:
                return notebook

        # (c) slash-separated path: catalog/schema/name.ipynb (or without extension)
        clean = path.replace("\\", "/").lstrip("/").rstrip("/")
        slash_parts = clean.split("/")
        if len(slash_parts) == 3:
            nb_name = slash_parts[2]
            if nb_name.endswith(".ipynb"):
                nb_name = nb_name[:-6]
            notebook = db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == slash_parts[0],
                UnifiedCatalogNotebook.schema_name == slash_parts[1],
                UnifiedCatalogNotebook.name == nb_name
            ).first()
            if notebook:
                return notebook

        # (d) bare notebook name
        notebook = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.name == path
        ).first()
        return notebook
    except SQLAlchemyError as exc:
        logger.error("Notebook catalog lookup failed for %s: %s", path, exc)
        raise HTTPException(status_code=500, detail=f"Catalog lookup failed: {exc}")


def _authorized_notebook(db, guard: Guard, path: str, privilege: Privilege):
    """Resolve ``path`` to a notebook the caller holds ``privilege`` on.

    Authorisation runs against the *resolved* record rather than the supplied
    path, because ``_resolve_catalog_notebook`` accepts a bare name and will
    match it in any catalog. Checking the input string would authorise a path
    the caller wrote while operating on whichever notebook the lookup landed
    on — not necessarily the same object.
    """
    notebook = _resolve_catalog_notebook(db, path)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found in catalog")
    guard.require(
        privilege,
        Securable.notebook(
            notebook.catalog_name, notebook.schema_name, notebook.name
        ),
    )
    return notebook


@router.delete("/files/{path:path}")
async def delete_notebook(
    path: str,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a .ipynb file from storage and remove its entry from catalog metadata."""
    from app.catalog.models import UnifiedCatalogSchema
    notebook = _authorized_notebook(db, guard, path, Privilege.MANAGE)
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _delete_notebook_file
    await _delete_notebook_file(db, schema, notebook.blob_path)
    db.delete(notebook)
    db.commit()
    return {"deleted": True, "path": path}


# ── File load/save ───────────────────────────────────────────────────────────

@router.get("/files/{path:path}")
async def load_notebook(
    path: str,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Load a .ipynb file. Response includes last_compute_resource_id and last_kernel_name in metadata."""
    from app.catalog.models import UnifiedCatalogSchema
    # SELECT, not BROWSE: the response is the notebook's full source and
    # stored cell outputs, which routinely contain query results.
    notebook = _authorized_notebook(db, guard, path, Privilege.SELECT)
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _notebook_exists, _read_notebook_content
    if not await _notebook_exists(db, schema, notebook.blob_path):
        raise HTTPException(status_code=404, detail="Notebook not found")
    content = await _read_notebook_content(db, schema, notebook.blob_path)
    # Inject catalog metadata so frontend can auto-reconnect to last compute and show info
    content["_catalog"] = {
        "id": notebook.id,
        "name": notebook.name,
        "catalog_name": notebook.catalog_name,
        "schema_name": notebook.schema_name,
        "created_at": notebook.created_at.isoformat() if notebook.created_at else None,
        "updated_at": notebook.updated_at.isoformat() if notebook.updated_at else None,
        "created_by": notebook.created_by,
        "updated_by": notebook.updated_by,
        "last_compute_resource_id": notebook.last_compute_resource_id,
        "last_kernel_name": notebook.last_kernel_name,
    }
    return JSONResponse(content=content)


@router.put("/files/{path:path}")
async def save_notebook(
    path: str,
    request_body: dict,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Save a .ipynb file."""
    from app.catalog.models import UnifiedCatalogSchema
    notebook = _authorized_notebook(db, guard, path, Privilege.EDIT)
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _write_notebook_content
    await _write_notebook_content(db, schema, notebook.blob_path, request_body)
    return {"saved": True, "path": path}


# ── MLflow Experiments & Runs ──────────────────────────────────────────────────

@router.get("/experiments/runs")
async def get_notebook_experiment_runs(
    path: str,
    max_results: int = 50,
    guard: Guard = Depends(get_guard),
):
    """Fetch MLflow experiment details and recent runs for a notebook."""
    import httpx
    from compassx.lookup import try_resolve_url

    clean_path = path.replace("\\", "/").strip("/")
    exp_candidates = [
        f"/{clean_path}",
        clean_path,
        f"/notebooks/{clean_path}",
    ]

    mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
    public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

    async with httpx.AsyncClient(timeout=4.0) as client:
        # Check health/reachability
        try:
            health_resp = await client.get(f"{mlflow_url}/health")
            if health_resp.status_code != 200:
                return {
                    "connected": False,
                    "message": f"MLflow server returned status {health_resp.status_code}",
                    "runs": [],
                }
        except Exception as exc:
            return {
                "connected": False,
                "message": f"MLflow tracking server is not reachable at {mlflow_url}",
                "runs": [],
            }

        # Try to find experiment by candidate names
        experiment = None
        for name in exp_candidates:
            try:
                resp = await client.get(
                    f"{mlflow_url}/api/2.0/mlflow/experiments/get-by-name",
                    params={"experiment_name": name},
                )
                if resp.status_code == 200:
                    experiment = resp.json().get("experiment")
                    break
            except Exception:
                pass

        if not experiment:
            return {
                "connected": True,
                "experiment": None,
                "ui_url": public_ui_url,
                "message": f"No MLflow experiment found for notebook '{clean_path}' yet.",
                "runs": [],
            }

        exp_id = experiment["experiment_id"]
        exp_ui_url = f"{public_ui_url}/#/experiments/{exp_id}"

        # Fetch runs
        runs_data = []
        try:
            search_resp = await client.post(
                f"{mlflow_url}/api/2.0/mlflow/runs/search",
                json={
                    "experiment_ids": [exp_id],
                    "max_results": max_results,
                    "order_by": ["attributes.start_time DESC"],
                },
            )
            if search_resp.status_code == 200:
                raw_runs = search_resp.json().get("runs", [])
                for r in raw_runs:
                    info = r.get("info", {})
                    data = r.get("data", {})
                    start_ms = info.get("start_time")
                    end_ms = info.get("end_time")
                    duration_ms = (end_ms - start_ms) if (start_ms and end_ms and end_ms >= start_ms) else None

                    metrics_map = {m["key"]: m["value"] for m in data.get("metrics", []) if "key" in m}
                    params_map = {p["key"]: p["value"] for p in data.get("params", []) if "key" in p}
                    tags_map = {t["key"]: t["value"] for t in data.get("tags", []) if "key" in t}

                    run_id = info.get("run_id")
                    runs_data.append({
                        "run_id": run_id,
                        "run_name": info.get("run_name") or run_id,
                        "status": info.get("status", "UNKNOWN"),
                        "start_time": start_ms,
                        "end_time": end_ms,
                        "duration_ms": duration_ms,
                        "artifact_uri": info.get("artifact_uri"),
                        "metrics": metrics_map,
                        "params": params_map,
                        "tags": tags_map,
                        "ui_url": f"{public_ui_url}/#/experiments/{exp_id}/runs/{run_id}",
                    })
        except Exception as exc:
            logger.warning("Failed to search MLflow runs for experiment %s: %s", exp_id, exc)

        return {
            "connected": True,
            "experiment": {
                "experiment_id": exp_id,
                "name": experiment.get("name"),
                "artifact_location": experiment.get("artifact_location"),
                "lifecycle_stage": experiment.get("lifecycle_stage"),
            },
            "ui_url": exp_ui_url,
            "total_runs": len(runs_data),
            "runs": runs_data,
        }


@router.get("/experiments/runs/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: str,
    path: str = "",
    guard: Guard = Depends(get_guard),
):
    """List artifacts for an MLflow run."""
    import httpx
    from compassx.lookup import try_resolve_url

    mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")

    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            resp = await client.get(
                f"{mlflow_url}/api/2.0/mlflow/artifacts/list",
                params={"run_id": run_id, "path": path},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "root_uri": data.get("root_uri"),
                    "files": data.get("files", []),
                }
            return {
                "connected": False,
                "message": f"MLflow returned status {resp.status_code}",
                "files": [],
            }
        except Exception as exc:
            return {
                "connected": False,
                "message": f"Failed to fetch artifacts: {exc}",
                "files": [],
            }


class RegisterModelRequest(BaseModel):
    run_id: str
    model_name: str
    artifact_path: str = "model"
    description: str = ""


@router.get("/experiments/models")
async def list_registered_models(
    max_results: int = 50,
    guard: Guard = Depends(get_guard),
):
    """List models registered in the MLflow Model Registry."""
    import httpx
    from compassx.lookup import try_resolve_url

    mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
    public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            health_resp = await client.get(f"{mlflow_url}/health")
            if health_resp.status_code != 200:
                return {
                    "connected": False,
                    "message": f"MLflow tracking server returned status {health_resp.status_code}",
                    "models": [],
                }
        except Exception:
            return {
                "connected": False,
                "message": f"MLflow tracking server is not reachable at {mlflow_url}",
                "models": [],
            }

        try:
            resp = await client.get(
                f"{mlflow_url}/api/2.0/mlflow/registered-models/search",
                params={"max_results": max_results},
            )
            if resp.status_code != 200:
                return {
                    "connected": True,
                    "models": [],
                    "message": f"Failed to retrieve models: {resp.text}",
                }

            raw_models = resp.json().get("registered_models", [])
            models_data = []
            for m in raw_models:
                name = m.get("name")
                versions = []
                for v in m.get("latest_versions", []):
                    versions.append({
                        "version": v.get("version"),
                        "creation_timestamp": v.get("creation_timestamp"),
                        "last_updated_timestamp": v.get("last_updated_timestamp"),
                        "current_stage": v.get("current_stage"),
                        "aliases": v.get("aliases", []),
                        "status": v.get("status"),
                        "source": v.get("source"),
                        "run_id": v.get("run_id"),
                        "ui_url": f"{public_ui_url}/#/models/{name}/versions/{v.get('version')}",
                    })
                tags_map = {t["key"]: t["value"] for t in m.get("tags", []) if "key" in t}
                models_data.append({
                    "name": name,
                    "creation_timestamp": m.get("creation_timestamp"),
                    "last_updated_timestamp": m.get("last_updated_timestamp"),
                    "description": m.get("description"),
                    "latest_versions": versions,
                    "tags": tags_map,
                    "ui_url": f"{public_ui_url}/#/models/{name}",
                })

            return {
                "connected": True,
                "models": models_data,
                "total_models": len(models_data),
            }
        except Exception as exc:
            return {
                "connected": False,
                "message": f"Error querying models: {exc}",
                "models": [],
            }


@router.post("/experiments/models/register")
async def register_model_version(
    payload: RegisterModelRequest,
    guard: Guard = Depends(get_guard),
):
    """Register a model artifact from an active or past run into the Model Registry."""
    import httpx
    from compassx.lookup import try_resolve_url

    mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
    public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

    clean_path = payload.artifact_path.strip("/")
    source = f"runs:/{payload.run_id}/{clean_path}" if clean_path else f"runs:/{payload.run_id}"

    async with httpx.AsyncClient(timeout=6.0) as client:
        # Step 1: Ensure registered model exists
        try:
            await client.post(
                f"{mlflow_url}/api/2.0/mlflow/registered-models/create",
                json={"name": payload.model_name, "description": payload.description},
            )
        except Exception:
            pass

        # Step 2: Create model version
        try:
            resp = await client.post(
                f"{mlflow_url}/api/2.0/mlflow/model-versions/create",
                json={
                    "name": payload.model_name,
                    "source": source,
                    "run_id": payload.run_id,
                    "description": payload.description,
                },
            )
            if resp.status_code in (200, 201):
                version_info = resp.json().get("model_version", {})
                version_num = version_info.get("version")
                return {
                    "success": True,
                    "model_name": payload.model_name,
                    "version": version_num,
                    "source": source,
                    "ui_url": f"{public_ui_url}/#/models/{payload.model_name}/versions/{version_num}",
                    "model_version": version_info,
                }
            else:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"MLflow error creating model version: {resp.text}",
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to communicate with MLflow Model Registry: {exc}",
            )


