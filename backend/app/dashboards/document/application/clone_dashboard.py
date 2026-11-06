import copy
import uuid
from typing import Dict

from fastapi import Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.models.dashboard import Dashboard
from app.dashboards.shared.support import (
    _authorized_dashboard,
    _default_schema,
    _register_dashboard,
    _to_full,
)


class CloneDashboard:
    def execute(self, request: Request, dashboard_id: str, db: Session, guard: Guard):
        # A clone copies the source's widgets and dataset SQL verbatim into an
        # object the caller will own, so it discloses everything BROWSE does —
        # and no more. The destination is authorised separately below.
        src = _authorized_dashboard(db, guard, dashboard_id, Privilege.BROWSE)
        new_id = str(uuid.uuid4())
        actor = guard.principal.id
        catalog, schema = _default_schema(db, guard, guard.workspace_id)

        new_pages = copy.deepcopy(src.pages or [])
        new_widgets = copy.deepcopy(src.widgets or [])
        new_datasets = copy.deepcopy(src.datasets or [])

        # Remap page and widget IDs so they're independent
        page_id_map: Dict[str, str] = {}
        for page in new_pages:
            old_id = page["id"]
            new_pid = str(uuid.uuid4())
            page_id_map[old_id] = new_pid
            page["id"] = new_pid
            page["dashboardId"] = new_id

        for widget in new_widgets:
            widget["id"] = str(uuid.uuid4())
            if widget.get("pageId") in page_id_map:
                widget["pageId"] = page_id_map[widget["pageId"]]

        for ds in new_datasets:
            ds["id"] = str(uuid.uuid4())
            ds["dashboardId"] = new_id

        clone = Dashboard(
            id=new_id,
            name=f"{src.name} (copy)",
            folder_id=src.folder_id,
            permission_mode=src.permission_mode,
            is_draft=True,
            pages=new_pages,
            widgets=new_widgets,
            datasets=new_datasets,
            settings=copy.deepcopy(src.settings),
            created_by=actor,
        )
        db.add(clone)
        db.flush()

        securable = _register_dashboard(
            db, catalog, schema, new_id, f"{src.name} (copy)", actor
        )
        guard.claim_ownership(securable)

        db.commit()
        db.refresh(clone)
        return _to_full(clone)


def clone_dashboard(request, dashboard_id, db, guard):
    return CloneDashboard().execute(request, dashboard_id, db, guard)
