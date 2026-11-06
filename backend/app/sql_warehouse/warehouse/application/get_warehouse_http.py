from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id


class GetWarehouseHttp:
    def execute(self, request: Request, warehouse_id: str, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        wh = get_warehouse_by_id(db, warehouse_id, workspace_id=workspace_id)
        if not wh:
            raise HTTPException(404, "Warehouse not found")
        return wh


def get_wh(request, warehouse_id, db, user):
    return GetWarehouseHttp().execute(request, warehouse_id, db, user)
