from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id
from app.sql_warehouse.warehouse.application.update_warehouse_status import update_warehouse_status
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator


class StopWarehouse:
    async def execute(self, request: Request, warehouse_id: str, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        wh = get_warehouse_by_id(db, warehouse_id, workspace_id=workspace_id)
        if not wh:
            raise HTTPException(404, "Warehouse not found")

        orchestrator = WarehousePodOrchestrator()
        await orchestrator.stop_pod(wh)
        return update_warehouse_status(db, warehouse_id, "stopped", workspace_id=workspace_id)


def stop_wh(request, warehouse_id, db, user):
    return StopWarehouse().execute(request, warehouse_id, db, user)
