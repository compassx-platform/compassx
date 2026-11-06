from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class ListWarehousesHttp:
    def execute(self, request: Request, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        from app.sql_warehouse.warehouse.manager import list_warehouses
        return list_warehouses(db, workspace_id=workspace_id)


def list_wh(request, db, user):
    return ListWarehousesHttp().execute(request, db, user)
