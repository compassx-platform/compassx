from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import _authorized_dashboard, _to_full


class UpdatePageLayout:
    def execute(self, dashboard_id: str, page_id: str, body, db: Session, guard: Guard):
        d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
        pages = d.pages or []
        found = False
        for page in pages:
            if page.get("id") == page_id:
                page["layout"] = body.layout
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="Page not found")
        d.pages = pages
        db.commit()
        db.refresh(d)
        return _to_full(d)


def update_page_layout(dashboard_id, page_id, body, db, guard):
    return UpdatePageLayout().execute(dashboard_id, page_id, body, db, guard)
