from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id
from app.sql_warehouse.warehouse.application.list_warehouses import list_warehouses


class SetDefaultWarehouse:
    def execute(self, db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse:
        target = get_warehouse_by_id(db, warehouse_id, workspace_id)
        if not target:
            raise HTTPException(404, "Warehouse not found")

        # Unset is_default on other warehouses in this workspace
        all_whs = list_warehouses(db, workspace_id)
        for wh in all_whs:
            if wh.id != target.id and wh.is_default:
                wh.is_default = False

        target.is_default = True
        target.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(target)
        return target


def set_default_warehouse(db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse:
    return SetDefaultWarehouse().execute(db, warehouse_id, workspace_id)
