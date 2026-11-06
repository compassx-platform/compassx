from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.shared.support import _resolve_user_and_workspace
from app.sql_warehouse.warehouse.manager import get_default_warehouse, get_warehouse_by_id
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator
from datetime import datetime, timezone


class RunQuery:
    async def execute(self, request: Request, req, db: Session, data_db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        warehouse = None
        if req.warehouse_id:
            warehouse = get_warehouse_by_id(db, req.warehouse_id, workspace_id=workspace_id)
        if not warehouse:
            warehouse = get_default_warehouse(db, workspace_id=workspace_id)
        if not warehouse:
            raise HTTPException(404, "No active or default warehouse found for this workspace")

        # Auto-resume warehouse pod if stopped or suspended
        if warehouse.status != "running":
            orchestrator = WarehousePodOrchestrator()
            runtime_id, endpoint = await orchestrator.start_pod(warehouse)
            warehouse.runtime_id = runtime_id
            warehouse.endpoint_url = endpoint
            warehouse.status = "running"
            warehouse.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(warehouse)

        try:
            result = await QueryExecutor(db, data_db).run(
                warehouse=warehouse,
                sql=req.sql,
                user_id=user_id,
                session_id=req.session_id,
                max_rows=req.max_rows,
                catalog=req.catalog,
                schema_name=req.schema_name,
                source=req.source,
            )
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"error": "Query execution failed", "detail": str(exc)}) from exc


def run_query(request, req, db, data_db, user):
    return RunQuery().execute(request, req, db, data_db, user)
