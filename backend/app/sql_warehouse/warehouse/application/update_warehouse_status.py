from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id
from app.sql_warehouse.warehouse.constants import VALID_STATUSES


class UpdateWarehouseStatus:
    def execute(self, db: Session, warehouse_id: str, status: str, workspace_id: str | None = None) -> SqlWarehouse:
        if status not in VALID_STATUSES:
            raise HTTPException(400, f"Unsupported warehouse status '{status}'.")
        warehouse = get_warehouse_by_id(db, warehouse_id, workspace_id)
        if not warehouse:
            raise HTTPException(404, "Warehouse not found")
        warehouse.status = status
        warehouse.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(warehouse)
        return warehouse


def update_warehouse_status(db: Session, warehouse_id: str, status: str, workspace_id: str | None = None) -> SqlWarehouse:
    return UpdateWarehouseStatus().execute(db, warehouse_id, status, workspace_id)
