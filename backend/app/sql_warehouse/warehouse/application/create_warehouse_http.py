from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.create_warehouse import create_warehouse
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator


class CreateWarehouseHttp:
    async def execute(self, request: Request, req, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        wh = create_warehouse(db, req, created_by=user_id, workspace_id=workspace_id)
        # Provision pod for the new warehouse
        orchestrator = WarehousePodOrchestrator()
        runtime_id, endpoint = await orchestrator.start_pod(wh)
        wh.runtime_id = runtime_id
        wh.endpoint_url = endpoint
        wh.status = "running"
        db.commit()
        db.refresh(wh)
        return wh


def create_wh(request, req, db, user):
    return CreateWarehouseHttp().execute(request, req, db, user)
