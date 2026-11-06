from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.query.query_record import QueryRecordStore
from app.sql_warehouse.shared.support import _record_to_dict, _resolve_user_and_workspace


class QueryHistory:
    def execute(self, request: Request, warehouse_id, limit, offset, status, scope, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        target_user_id = user_id if scope == "me" else None
        records = QueryRecordStore(db).list(user_id=target_user_id, warehouse_id=warehouse_id, status=status, limit=limit, offset=offset)
        return {"records": [_record_to_dict(r) for r in records], "limit": limit, "offset": offset}


def query_history(request, warehouse_id, limit, offset, status, scope, db, user):
    return QueryHistory().execute(request, warehouse_id, limit, offset, status, scope, db, user)
