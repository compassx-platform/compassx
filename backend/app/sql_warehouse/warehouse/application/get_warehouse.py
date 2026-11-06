from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse


class GetWarehouse:
    def execute(self, db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse | None:
        stmt = select(SqlWarehouse).filter(SqlWarehouse.id == warehouse_id)
        if workspace_id:
            stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
        else:
            stmt = stmt.filter(SqlWarehouse.workspace_id == None)
        return db.scalars(stmt).first()


def get_warehouse_by_id(db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse | None:
    return GetWarehouse().execute(db, warehouse_id, workspace_id)
