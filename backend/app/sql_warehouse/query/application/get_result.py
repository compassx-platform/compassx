from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.sql_warehouse.query.query_record import QueryRecordStore
from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class GetResult:
    def execute(self, query_id: str, request: Request, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        record = QueryRecordStore(db).get(query_id)
        if not record:
            raise HTTPException(404, "Query not found")
        if record.user_id != user_id:
            raise HTTPException(403, "Forbidden")
        if record.result_payload:
            return {**record.result_payload, "query_id": query_id, "cache_hit": record.cache_hit, "query_analysis": record.query_analysis}
        return {"query_id": query_id, "status": record.status, "message": "Result no longer available. Re-run the query."}


def get_result(query_id, request, db, user):
    return GetResult().execute(query_id, request, db, user)
