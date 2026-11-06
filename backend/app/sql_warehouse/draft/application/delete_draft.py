from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlDraftQuery
from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class DeleteDraft:
    def execute(self, draft_id: str, request: Request, db: Session, user):
        user_id, workspace_id = _resolve_user_and_workspace(request, user)
        stmt = select(SqlDraftQuery).where(
            SqlDraftQuery.id == draft_id,
            SqlDraftQuery.user_id == user_id,
        )
        if workspace_id:
            stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
        else:
            stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))

        draft = db.scalar(stmt)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft query not found")

        db.delete(draft)
        db.commit()
        return {"deleted": True, "id": draft_id}


def delete_draft(draft_id, request, db, user):
    return DeleteDraft().execute(draft_id, request, db, user)
