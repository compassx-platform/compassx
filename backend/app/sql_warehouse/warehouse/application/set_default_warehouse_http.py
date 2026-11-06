from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.set_default_warehouse import set_default_warehouse


class SetDefaultWarehouseHttp:
    def execute(self, request: Request, warehouse_id: str, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        return set_default_warehouse(db, warehouse_id, workspace_id=workspace_id)


def set_default_wh(request, warehouse_id, db, user):
    return SetDefaultWarehouseHttp().execute(request, warehouse_id, db, user)
