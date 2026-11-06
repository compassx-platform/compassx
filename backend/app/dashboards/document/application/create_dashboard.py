import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.models.dashboard import Dashboard
from app.dashboards.shared.support import _default_schema, _register_dashboard, _to_full


class CreateDashboard:
    def execute(self, request: Request, body, db: Session, guard: Guard):
        dash_id = str(uuid.uuid4())
        first_page_id = str(uuid.uuid4())
        actor = guard.principal.id
        workspace_id = guard.workspace_id
        # Resolve and authorise the destination schema before writing anything:
        # a dashboard that cannot be registered has no catalog path, and an
        # object with no path is one no grant can ever reach.
        catalog, schema = _default_schema(db, guard, workspace_id)

        d = Dashboard(
            id=dash_id,
            name=body.name,
            folder_id=body.folderId,
            permission_mode=body.permissionMode,
            is_draft=True,
            pages=[{
                "id": first_page_id,
                "dashboardId": dash_id,
                "name": "Page 1",
                "order": 0,
                "layout": [],
            }],
            widgets=[],
            datasets=[],
            settings=None,
            created_by=actor,
        )
        db.add(d)
        db.flush()

        securable = _register_dashboard(db, catalog, schema, dash_id, body.name, actor)
        guard.claim_ownership(securable)

        db.commit()
        db.refresh(d)
        return _to_full(d)


def create_dashboard(request, body, db, guard):
    return CreateDashboard().execute(request, body, db, guard)
