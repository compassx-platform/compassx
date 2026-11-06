from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.engine.router import get_adapter
from app.sql_warehouse.query.query_record import QueryRecordStore
from app.sql_warehouse.warehouse.manager import get_warehouse_by_id


class CancelQuery:
    async def execute(self, request: Request, req, db: Session, data_db: Session, user):
        del user
        workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
        records = QueryRecordStore(data_db)
        active = records.get_active(req.query_id)
        if not active:
            raise HTTPException(404, "Query not found or already completed")
        warehouse = get_warehouse_by_id(db, active.warehouse_id, workspace_id=workspace_id)
        if not warehouse:
            raise HTTPException(404, "Warehouse not found")
        await get_adapter(warehouse).cancel(active.engine_query_id or active.query_id)
        records.set_status(req.query_id, "cancelled")
        records.deregister_active(req.query_id)
        return {"cancelled": True, "query_id": req.query_id}


def cancel_query(request, req, db, data_db, user):
    return CancelQuery().execute(request, req, db, data_db, user)
