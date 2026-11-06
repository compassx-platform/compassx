from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.delete_warehouse import delete_warehouse
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator


class DeleteWarehouseHttp:
    async def execute(self, request: Request, warehouse_id: str, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        wh = get_warehouse_by_id(db, warehouse_id, workspace_id=workspace_id)
        if not wh:
            raise HTTPException(404, "Warehouse not found")

        orchestrator = WarehousePodOrchestrator()
        await orchestrator.delete_pod(wh)
        delete_warehouse(db, warehouse_id, workspace_id=workspace_id)
        return {"deleted": True}


def delete_wh(request, warehouse_id, db, user):
    return DeleteWarehouseHttp().execute(request, warehouse_id, db, user)
