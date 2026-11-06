from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlDraftQuery
from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class CreateDraft:
    def execute(self, request: Request, req, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)

        # Resolve default query name if none or empty provided
        name = (req.name or "").strip()
        if not name:
            stmt = select(func.count()).select_from(SqlDraftQuery).where(SqlDraftQuery.user_id == user_id)
            if workspace_id:
                stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
            else:
                stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))
            count = db.scalar(stmt) or 0
            name = f"Query {count + 1}"

        draft = SqlDraftQuery(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            sql_text=req.sql_text or "",
            catalog=req.catalog or "",
            schema_name=req.schema_name or "",
            tab_order=req.tab_order,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft


def create_draft(request, req, db, user):
    return CreateDraft().execute(request, req, db, user)
