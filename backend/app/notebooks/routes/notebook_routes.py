"""
Notebook routes (prefix: /api/v1/notebook).

Handlers stay here. Each one forwards to one application type.
Helper names stay importable from this module.
"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_account_db
from app.dependencies import get_current_user
from app.governance.dependencies import Guard, get_guard

from compute.config import compute_settings
from services.storage.fs import get_fs

from app.notebooks.document.application.create_notebook import create_notebook as create_notebook_action
from app.notebooks.document.application.delete_notebook import delete_notebook as delete_notebook_action
from app.notebooks.document.application.get_notebook_config import get_notebook_config as get_notebook_config_action
from app.notebooks.document.application.list_notebooks import list_notebooks as list_notebooks_action
from app.notebooks.document.application.load_notebook import load_notebook as load_notebook_action
from app.notebooks.document.application.save_notebook import save_notebook as save_notebook_action
from app.notebooks.document.application.save_notebook_compute import save_notebook_compute as save_notebook_compute_action
from app.notebooks.experiment.application.get_notebook_experiment_runs import (
    get_notebook_experiment_runs as get_notebook_experiment_runs_action,
)
from app.notebooks.experiment.application.get_run_artifacts import get_run_artifacts as get_run_artifacts_action
from app.notebooks.experiment.application.list_registered_models import (
    list_registered_models as list_registered_models_action,
)
from app.notebooks.experiment.application.register_model_version import (
    register_model_version as register_model_version_action,
)
from app.notebooks.shared.support import (
    JUPYTER_TOKEN,
    _JUPYTER_PROXY_PATH,
    _NOTEBOOKS_BUCKET,
    _NOTEBOOKS_PREFIX,
    _authorized_notebook,
    _catalog_storage_location,
    _jupyter_base_url,
    _jupyter_ws_url,
    _key_to_rel,
    _resolve_catalog_notebook,
    _safe_key,
)

router = APIRouter(prefix="/api/v1/notebook", tags=["notebook"])
logger = logging.getLogger(__name__)


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
    return get_notebook_config_action(request, guard)


@router.get("/list")
def list_notebooks(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List catalog notebooks visible in the active workspace."""
    return list_notebooks_action(request, db, guard)


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
    return save_notebook_compute_action(notebook_id, body, db, guard)


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
    return await create_notebook_action(body, request, db, user, guard)


@router.delete("/files/{path:path}")
async def delete_notebook(
    path: str,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a .ipynb file from storage and remove its entry from catalog metadata."""
    return await delete_notebook_action(path, db, guard)


@router.get("/files/{path:path}")
async def load_notebook(
    path: str,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Load a .ipynb file. Response includes last_compute_resource_id and last_kernel_name in metadata."""
    return await load_notebook_action(path, db, guard)


@router.put("/files/{path:path}")
async def save_notebook(
    path: str,
    request_body: dict,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Save a .ipynb file."""
    return await save_notebook_action(path, request_body, db, guard)


@router.get("/experiments/runs")
async def get_notebook_experiment_runs(
    path: str,
    max_results: int = 50,
    guard: Guard = Depends(get_guard),
):
    """Fetch MLflow experiment details and recent runs for a notebook."""
    return await get_notebook_experiment_runs_action(path, max_results, guard)


@router.get("/experiments/runs/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: str,
    path: str = "",
    guard: Guard = Depends(get_guard),
):
    """List artifacts for an MLflow run."""
    return await get_run_artifacts_action(run_id, path, guard)


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
    return await list_registered_models_action(max_results, guard)


@router.post("/experiments/models/register")
async def register_model_version(
    payload: RegisterModelRequest,
    guard: Guard = Depends(get_guard),
):
    """Register a model artifact from an active or past run into the Model Registry."""
    return await register_model_version_action(payload, guard)
