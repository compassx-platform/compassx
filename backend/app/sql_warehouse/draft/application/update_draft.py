from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlDraftQuery
from app.sql_warehouse.shared.support import _resolve_user_and_workspace


class UpdateDraft:
    def execute(self, draft_id: str, req, request: Request, db: Session, user):
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

        if req.name is not None:
            trimmed_name = req.name.strip()
            if trimmed_name:
                draft.name = trimmed_name
        if req.sql_text is not None:
            draft.sql_text = req.sql_text
        if req.catalog is not None:
            draft.catalog = req.catalog
        if req.schema_name is not None:
            draft.schema_name = req.schema_name
        if req.tab_order is not None:
            draft.tab_order = req.tab_order

        db.commit()
        db.refresh(draft)
        return draft


def update_draft(draft_id, req, request, db, user):
    return UpdateDraft().execute(draft_id, req, request, db, user)
