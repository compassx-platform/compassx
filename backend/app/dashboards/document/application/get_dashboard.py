from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard, _to_full


class GetDashboard:
    def execute(self, dashboard_id: str, db: Session, guard: Guard):
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.BROWSE)
        return _to_full(d)


def get_dashboard(dashboard_id, db, guard):
    return GetDashboard().execute(dashboard_id, db, guard)
