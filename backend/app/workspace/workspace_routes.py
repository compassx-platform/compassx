"""Workspace-scoped APIs: /api/w/{slug}/api/...

- Workspace info + current user role
- Member management
- Catalog visibility (list objects, publish)
"""

from __future__ import annotations

import logging

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.database import get_account_db

from app.workspace.auth import get_current_principal

from app.workspace.middleware import WorkspaceContext

from app.workspace.models import (
    CatalogObject,
    CatalogPermission,
    Principal,
    Workspace,
    WorkspaceCatalog,
    WorkspaceMembership,
)

from app.workspace.schemas import (
    CatalogObjectOut,
    MemberAdd,
    MemberOut,
    MemberPatch,
    WorkspaceSlim,
)

logger = logging.getLogger("app.workspace.workspace_routes")

router = APIRouter(prefix="/api/w/{slug}/api", tags=["workspace"])

def _get_workspace_ctx(request: Request) -> WorkspaceContext:
    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        raise HTTPException(status_code=400, detail="Missing workspace context")
    return ctx

def _require_workspace_admin(ctx: WorkspaceContext) -> None:
    if ctx.principal_role not in ("admin",) and not ctx.is_account_admin:
        raise HTTPException(status_code=403, detail="Workspace admin required")

DEFAULT_WORKSPACE_SETTINGS = {
    "default_warehouse": "last_selected",
    "serverless_interactive_timeout": 9000,
    "package_repositories": {
        "pypi_index_url": "https://pypi.org/simple",
        "pypi_extra_index_urls": [],
        "npm_registry": "https://registry.npmjs.org/",
        "maven_central": "https://repo1.maven.org/maven2/",
        "custom_repositories": []
    },
    "base_environments": {
        "python_version": "3.11",
        "spark_version": "3.5.0",
        "preinstalled_packages": [
            "pandas>=2.0.0",
            "numpy>=1.24.0",
            "scikit-learn>=1.3.0",
            "plotly>=5.15.0",
            "requests>=2.31.0"
        ],
        "environment_variables": {
            "PYTHONUNBUFFERED": "1"
        }
    },
    "serverless_usage_policies": {
        "enforce_cost_tags": True,
        "required_tags": ["Environment", "CostCenter", "Project"],
        "max_runtime_hours_per_day": 24,
        "max_concurrent_queries": 10,
        "cost_alert_threshold": 1000
    },
    "classic_compute_policies": {
        "allow_unrestricted_cluster_creation": False,
        "default_node_type": "standard_d4s_v5",
        "max_nodes": 8,
        "auto_termination_minutes": 60,
        "cluster_tags": {
            "ManagedBy": "CompassX",
            "Tier": "Workspace"
        }
    }
}

import app.workspace.http.workspace.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.workspace.http.workspace.application.get_workspace_info import get_workspace_info as get_workspace_info_action
from app.workspace.http.workspace.application.get_workspace_settings import get_workspace_settings as get_workspace_settings_action
from app.workspace.http.workspace.application.update_workspace_settings import update_workspace_settings as update_workspace_settings_action
from app.workspace.http.workspace.application.list_members import list_members as list_members_action
from app.workspace.http.workspace.application.add_member import add_member as add_member_action
from app.workspace.http.workspace.application.update_member_role import update_member_role as update_member_role_action
from app.workspace.http.workspace.application.remove_member import remove_member as remove_member_action
from app.workspace.http.workspace.application.list_catalogs import list_catalogs as list_catalogs_action
from app.workspace.http.workspace.application.list_schemas import list_schemas as list_schemas_action
from app.workspace.http.workspace.application.list_objects import list_objects as list_objects_action
from app.workspace.http.workspace.application.publish_object import publish_object as publish_object_action

router = APIRouter(prefix="/api/w/{slug}/api", tags=["workspace"])


@router.get("/workspace")
def get_workspace_info(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return get_workspace_info_action(slug=slug, request=request, db=db)


@router.get("/workspace/settings")
def get_workspace_settings(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return get_workspace_settings_action(slug=slug, request=request, db=db)


@router.patch("/workspace/settings")
def update_workspace_settings(
    slug: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return update_workspace_settings_action(slug=slug, body=body, request=request, db=db)


@router.get("/workspace/members", response_model=list[MemberOut])
def list_members(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return list_members_action(slug=slug, request=request, db=db)


@router.post("/workspace/members", response_model=MemberOut, status_code=201)
def add_member(
    slug: str,
    body: MemberAdd,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return add_member_action(slug=slug, body=body, request=request, db=db)


@router.patch("/workspace/members/{member_id}", response_model=MemberOut)
def update_member_role(
    slug: str,
    member_id: str,
    body: MemberPatch,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return update_member_role_action(slug=slug, member_id=member_id, body=body, request=request, db=db)


@router.delete("/workspace/members/{member_id}", status_code=204)
def remove_member(
    slug: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return remove_member_action(slug=slug, member_id=member_id, request=request, db=db)


@router.get("/catalog", response_model=list[dict])
def list_catalogs(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return list_catalogs_action(slug=slug, request=request, db=db)


@router.get("/catalog/{catalog_name}/schemas")
def list_schemas(
    slug: str,
    catalog_name: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return list_schemas_action(slug=slug, catalog_name=catalog_name, request=request, db=db)


@router.get("/catalog/{catalog_name}/{schema_name}/objects", response_model=list[CatalogObjectOut])
def list_objects(
    slug: str,
    catalog_name: str,
    schema_name: str,
    request: Request,
    object_type: str | None = None,
    db: Session = Depends(get_account_db),
):
    return list_objects_action(slug=slug, catalog_name=catalog_name, schema_name=schema_name, request=request, object_type=object_type, db=db)


@router.post("/catalog/objects/{object_id}/publish", status_code=200)
def publish_object(
    slug: str,
    object_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    return publish_object_action(slug=slug, object_id=object_id, request=request, db=db)
