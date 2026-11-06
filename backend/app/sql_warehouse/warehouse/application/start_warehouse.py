from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.get_warehouse import get_warehouse_by_id
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator


class StartWarehouse:
    async def execute(self, request: Request, warehouse_id: str, db: Session, user):
        _user_id, workspace_id = _resolve_user_and_workspace(request, user)
        wh = get_warehouse_by_id(db, warehouse_id, workspace_id=workspace_id)
        if not wh:
            raise HTTPException(404, "Warehouse not found")

        wh.status = "starting"
        wh.updated_at = datetime.now(timezone.utc)
        db.commit()

        orchestrator = WarehousePodOrchestrator()
        runtime_id, endpoint = await orchestrator.start_pod(wh)
        wh.runtime_id = runtime_id
        wh.endpoint_url = endpoint
        wh.status = "running"
        wh.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(wh)
        return wh


def start_wh(request, warehouse_id, db, user):
    return StartWarehouse().execute(request, warehouse_id, db, user)
