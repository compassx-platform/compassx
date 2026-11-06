from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard, _to_full


class DiscardDraft:
    def execute(self, dashboard_id: str, db: Session, guard: Guard):
        """Discard draft edits — resets is_draft to True (no snapshot store for v1)."""
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
        d.is_draft = True
        db.commit()
        db.refresh(d)
        return _to_full(d)


def discard_draft(dashboard_id, db, guard):
    return DiscardDraft().execute(dashboard_id, db, guard)
