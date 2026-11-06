from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlDraftQuery
from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class ListDrafts:
    def execute(self, request: Request, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        stmt = select(SqlDraftQuery).where(SqlDraftQuery.user_id == user_id)
        if workspace_id:
            stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
        else:
            stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))
        stmt = stmt.order_by(SqlDraftQuery.tab_order.asc(), SqlDraftQuery.created_at.asc())
        return list(db.scalars(stmt))


def list_drafts(request, db, user):
    return ListDrafts().execute(request, db, user)
