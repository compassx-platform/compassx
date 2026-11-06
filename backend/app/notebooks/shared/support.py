"""Notebook path, catalog lookup, and Jupyter URL helpers."""
from __future__ import annotations

import logging
import os

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from services.storage.config import storage_settings

logger = logging.getLogger("app.notebooks.routes.notebook_routes")

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
