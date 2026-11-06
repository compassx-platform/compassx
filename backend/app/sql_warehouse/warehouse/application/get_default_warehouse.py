from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse


class GetDefaultWarehouse:
    def execute(self, db: Session, workspace_id: str | None = None) -> SqlWarehouse | None:
        stmt = select(SqlWarehouse)
        if workspace_id:
            stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
        else:
            stmt = stmt.filter(SqlWarehouse.workspace_id == None)

        # 1. Prefer warehouse explicitly marked as is_default
        wh = db.scalars(stmt.filter(SqlWarehouse.is_default == True)).first()
        if wh:
            return wh

        # 2. Fall back to name == "default"
        wh = db.scalars(stmt.filter(SqlWarehouse.name == "default")).first()
        if wh:
            return wh

        # 3. Fall back to first created
        return db.scalars(stmt.order_by(SqlWarehouse.created_at.asc())).first()


def get_default_warehouse(db: Session, workspace_id: str | None = None) -> SqlWarehouse | None:
    return GetDefaultWarehouse().execute(db, workspace_id)
