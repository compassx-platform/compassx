from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.engine.router import get_adapter
from app.sql_warehouse.warehouse.manager import get_default_warehouse, get_warehouse_by_id


class ExplainQuery:
    async def execute(self, request: Request, req, db: Session, user):
        del user
        workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
        warehouse = None
        if req.warehouse_id:
            warehouse = get_warehouse_by_id(db, req.warehouse_id, workspace_id=workspace_id)
        if not warehouse:
            warehouse = get_default_warehouse(db, workspace_id=workspace_id)
        if not warehouse:
            raise HTTPException(404, "Warehouse not found")
        return {"plan": await get_adapter(warehouse).explain(req.sql)}


def explain_query(request, req, db, user):
    return ExplainQuery().execute(request, req, db, user)
