from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard, _to_full


class PublishDashboard:
    def execute(self, dashboard_id: str, db: Session, guard: Guard):
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
        d.is_draft = False
        d.published_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(d)
        return _to_full(d)


def publish_dashboard(dashboard_id, db, guard):
    return PublishDashboard().execute(dashboard_id, db, guard)
