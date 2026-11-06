from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id


class DeleteWarehouse:
    def execute(self, db: Session, warehouse_id: str, workspace_id: str | None = None) -> None:
        warehouse = get_warehouse_by_id(db, warehouse_id, workspace_id)
        if not warehouse:
            raise HTTPException(404, "Warehouse not found")
        db.delete(warehouse)
        db.commit()


def delete_warehouse(db: Session, warehouse_id: str, workspace_id: str | None = None) -> None:
    return DeleteWarehouse().execute(db, warehouse_id, workspace_id)
