from fastapi import Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.models.dashboard import Dashboard
from app.dashboards.shared.support import _to_meta


class ListDashboards:
    def execute(self, request: Request, db: Session, guard: Guard):
        from app.catalog.models import (
            UnifiedCatalogDashboard,
            CatalogWorkspaceBinding,
            UnifiedCatalogSchema,
        )

        dashboards = db.query(Dashboard).order_by(Dashboard.updated_at.desc()).all()
        uc_query = db.query(UnifiedCatalogDashboard).filter(UnifiedCatalogDashboard.dashboard_id.isnot(None))

        workspace = getattr(request.state, "workspace", None)
        workspace_id = workspace.workspace_id if workspace else getattr(guard, "workspace_id", None)
        if workspace_id:
            catalog_ids = db.query(CatalogWorkspaceBinding.catalog_id).filter(
                CatalogWorkspaceBinding.workspace_id == str(workspace_id),
            )
            uc_query = uc_query.filter(
                UnifiedCatalogDashboard.schema.has(
                    UnifiedCatalogSchema.catalog_id.in_(catalog_ids)
                )
            )

        uc_dashboards = uc_query.all()
        uc_map = {uc.dashboard_id: uc for uc in uc_dashboards}
        # Unregistered dashboards have no catalog path and therefore no grants;
        # they are excluded rather than shown to everyone.
        visible = [
            d
            for d in dashboards
            if d.id in uc_map
            and guard.can(
                Privilege.BROWSE,
                Securable.dashboard(
                    uc_map[d.id].catalog_name, uc_map[d.id].schema_name, uc_map[d.id].name
                ),
            )
        ]
        return [_to_meta(d, uc_map.get(d.id)) for d in visible]


def list_dashboards(request, db, guard):
    return ListDashboards().execute(request, db, guard)
