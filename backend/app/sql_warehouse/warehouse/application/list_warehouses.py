from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse


class ListWarehouses:
    def execute(self, db: Session, workspace_id: str | None = None) -> list[SqlWarehouse]:
        stmt = select(SqlWarehouse)
        if workspace_id:
            stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
        else:
            stmt = stmt.filter(SqlWarehouse.workspace_id == None)
        return list(db.scalars(stmt.order_by(SqlWarehouse.created_at.desc())))


def list_warehouses(db: Session, workspace_id: str | None = None) -> list[SqlWarehouse]:
    return ListWarehouses().execute(db, workspace_id)
