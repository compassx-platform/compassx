"""Helper to ensure workspace-level default compute resources and SQL warehouses."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.compute_resources import ComputeResource
from app.sql_warehouse.models import SqlWarehouse
from compute.config import compute_settings
from compute.schemas import ComputeProfileId, ComputeResourceRequest, RuntimeType

logger = logging.getLogger(__name__)


def ensure_workspace_default_resources(
    system_db: Session,
    workspace_id: str | None = None,
    created_by: str = "system",
    user_id: str | None = None,
    runtime_manager=None,
) -> dict:
    """Ensure that a workspace (or global context if workspace_id is None) has a
    default DuckDB compute resource and a default DuckDB SQL warehouse.

    Rules:
    - Compute: If NO compute resource exists for the workspace, create one named
      'default' with duckdb runtime, default profile, and start it automatically.
      If any compute exists in the workspace, do not create or start.
    - SQL Warehouse: If NO SQL warehouse exists for the workspace, create one named
      'default' with duckdb engine and start it automatically (status='running').
      If any warehouse exists in the workspace, do not create or start.
    """
    from compute.resource_service import ComputeResourceService

    eff_user_id = user_id or compute_settings.DEFAULT_COMPUTE_USER_ID or "default"
    eff_created_by = created_by or compute_settings.DEFAULT_COMPUTE_CREATED_BY or "system"

    result = {
        "compute_created": False,
        "compute_id": None,
        "warehouse_created": False,
        "warehouse_id": None,
    }

    # ── 1. Compute Resource Check & Auto-Creation ────────────────────────────
    try:
        compute_query = system_db.query(ComputeResource)
        if workspace_id:
            compute_query = compute_query.filter(ComputeResource.workspace_id == workspace_id)
        else:
            compute_query = compute_query.filter(ComputeResource.workspace_id == None)

        existing_compute = compute_query.first()
        if existing_compute is None:
            logger.info("No compute resources found for workspace %s. Creating default DuckDB compute...", workspace_id)
            service = ComputeResourceService(system_db, runtime_manager=runtime_manager)
            profile_name = compute_settings.resolved_default_compute_profile()
            
            # Map profile_name to enum if needed
            try:
                profile_enum = ComputeProfileId(profile_name)
            except Exception:
                profile_enum = ComputeProfileId.LOCAL

            req = ComputeResourceRequest(
                name="default",
                runtime=RuntimeType.DUCKDB,
                profile=profile_enum,
                description="Auto-created default DuckDB compute.",
            )
            created = service.create_resource(
                req,
                user_id=eff_user_id,
                created_by=eff_created_by,
                workspace_id=workspace_id,
                is_default=True,
                auto_start=True,
            )
            result["compute_created"] = True
            result["compute_id"] = created.id
            logger.info("Created and auto-started default DuckDB compute resource %s for workspace %s", created.id, workspace_id)
        else:
            logger.debug("Compute resource already exists for workspace %s (found %s). Skipping default compute creation.", workspace_id, existing_compute.id)
    except Exception as exc:
        system_db.rollback()
        logger.error("Failed ensuring default compute resource for workspace %s: %s", workspace_id, exc)

    # ── 2. SQL Warehouse Check & Auto-Creation ───────────────────────────────
    try:
        wh_query = system_db.query(SqlWarehouse)
        if workspace_id:
            wh_query = wh_query.filter(SqlWarehouse.workspace_id == workspace_id)
        else:
            wh_query = wh_query.filter(SqlWarehouse.workspace_id == None)

        existing_wh = wh_query.first()
        if existing_wh is None:
            logger.info("No SQL warehouse found for workspace %s. Creating default DuckDB SQL warehouse...", workspace_id)
            wh = SqlWarehouse(
                workspace_id=workspace_id,
                name="default",
                description="Default DuckDB SQL Warehouse",
                engine="duckdb",
                status="running",
                config={},
                resource_policy={},
                created_by=eff_created_by,
            )
            system_db.add(wh)
            system_db.commit()
            system_db.refresh(wh)
            result["warehouse_created"] = True
            result["warehouse_id"] = wh.id
            logger.info("Created and auto-started default DuckDB SQL warehouse %s for workspace %s", wh.id, workspace_id)
        else:
            logger.debug("SQL warehouse already exists for workspace %s (found %s). Skipping default warehouse creation.", workspace_id, existing_wh.id)
    except Exception as exc:
        system_db.rollback()
        logger.error("Failed ensuring default SQL warehouse for workspace %s: %s", workspace_id, exc)

    return result
