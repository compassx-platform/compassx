from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard


class DeleteDashboard:
    def execute(self, dashboard_id: str, db: Session, guard: Guard):
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.MANAGE)
        from app.catalog.models import UnifiedCatalogDashboard
        db.query(UnifiedCatalogDashboard).filter(UnifiedCatalogDashboard.dashboard_id == dashboard_id).delete()
        db.delete(d)
        db.commit()


def delete_dashboard(dashboard_id, db, guard):
    return DeleteDashboard().execute(dashboard_id, db, guard)
