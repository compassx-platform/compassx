from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.warehouse.application.list_warehouses import list_warehouses
from app.sql_warehouse.warehouse.constants import VALID_ENGINES


class CreateWarehouse:
    def execute(self, db: Session, req, created_by: str, workspace_id: str | None = None) -> SqlWarehouse:
        if req.engine not in VALID_ENGINES:
            raise HTTPException(400, f"Unsupported engine '{req.engine}'.")

        # If this is the first warehouse in the workspace, or explicitly requested as default
        existing = list_warehouses(db, workspace_id)
        should_be_default = getattr(req, "is_default", False) or len(existing) == 0

        if should_be_default:
            for wh in existing:
                if wh.is_default:
                    wh.is_default = False

        warehouse = SqlWarehouse(
            workspace_id=workspace_id,
            name=req.name,
            description=req.description,
            engine=req.engine,
            is_default=should_be_default,
            config=req.config,
            resource_policy=req.resource_policy,
            created_by=created_by,
        )
        db.add(warehouse)
        db.commit()
        db.refresh(warehouse)
        return warehouse


def create_warehouse(db: Session, req, created_by: str, workspace_id: str | None = None) -> SqlWarehouse:
    return CreateWarehouse().execute(db, req, created_by, workspace_id)
