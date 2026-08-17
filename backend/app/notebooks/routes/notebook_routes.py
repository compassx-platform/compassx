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


@router.get("/config", response_model=NotebookServerConfig)
def get_notebook_config():
    """Return jupyter_server connection settings for the frontend."""
    return NotebookServerConfig(
        base_url=_jupyter_base_url(),
        ws_url=_jupyter_ws_url(),
        token=JUPYTER_TOKEN,
    )


# ── List / Create / Delete ───────────────────────────────────────────────────

@router.get("/list")
def list_notebooks(
    request: Request,
    db: Session = Depends(get_account_db),
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
):
    """Save the last-connected compute resource and kernel name for a notebook."""
    from app.catalog.models import UnifiedCatalogNotebook

    notebook = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.id == notebook_id
    ).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")

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


@router.delete("/files/{path:path}")
async def delete_notebook(path: str, db: Session = Depends(get_account_db)):
    """Delete a .ipynb file from storage and remove its entry from catalog metadata."""
    from app.catalog.models import UnifiedCatalogSchema
    notebook = _resolve_catalog_notebook(db, path)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found in catalog")
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _delete_notebook_file
    await _delete_notebook_file(db, schema, notebook.blob_path)
    db.delete(notebook)
    db.commit()
    return {"deleted": True, "path": path}


# ── File load/save ───────────────────────────────────────────────────────────

@router.get("/files/{path:path}")
async def load_notebook(path: str, db: Session = Depends(get_account_db)):
    """Load a .ipynb file. Response includes last_compute_resource_id and last_kernel_name in metadata."""
    from app.catalog.models import UnifiedCatalogSchema
    notebook = _resolve_catalog_notebook(db, path)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found in catalog")
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _notebook_exists, _read_notebook_content
    if not await _notebook_exists(db, schema, notebook.blob_path):
        raise HTTPException(status_code=404, detail="Notebook not found")
    content = await _read_notebook_content(db, schema, notebook.blob_path)
    # Inject catalog metadata so frontend can auto-reconnect to last compute
    content["_catalog"] = {
        "id": notebook.id,
        "last_compute_resource_id": notebook.last_compute_resource_id,
        "last_kernel_name": notebook.last_kernel_name,
    }
    return JSONResponse(content=content)


@router.put("/files/{path:path}")
async def save_notebook(path: str, request_body: dict, db: Session = Depends(get_account_db)):
    """Save a .ipynb file."""
    from app.catalog.models import UnifiedCatalogSchema
    notebook = _resolve_catalog_notebook(db, path)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found in catalog")
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    from app.catalog.service import _write_notebook_content
    await _write_notebook_content(db, schema, notebook.blob_path, request_body)
    return {"saved": True, "path": path}

