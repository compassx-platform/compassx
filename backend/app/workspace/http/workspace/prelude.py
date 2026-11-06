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
