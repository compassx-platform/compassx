from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard, _rename_registration, _to_full


class SaveDashboard:
    def execute(self, dashboard_id: str, body, db: Session, guard: Guard):
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
        if body.name is not None and body.name != d.name:
            _rename_registration(db, guard, dashboard_id, body.name)
        if body.name is not None:
            d.name = body.name
        if body.pages is not None:
            d.pages = body.pages
        if body.widgets is not None:
            d.widgets = body.widgets
        if body.datasets is not None:
            d.datasets = body.datasets
        if body.settings is not None:
            d.settings = body.settings
        if body.permissionMode is not None:
            d.permission_mode = body.permissionMode
        if body.folderId is not None:
            d.folder_id = body.folderId
        db.commit()
        db.refresh(d)
        return _to_full(d)


def save_dashboard(dashboard_id, body, db, guard):
    return SaveDashboard().execute(dashboard_id, body, db, guard)
