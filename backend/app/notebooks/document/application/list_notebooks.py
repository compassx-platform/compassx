from fastapi import Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.notebooks.shared.support import _catalog_storage_location


class ListNotebooks:
    def execute(self, request: Request, db: Session, guard: Guard):
        from app.catalog.models import (
            CatalogWorkspaceBinding,
            UnifiedCatalogNotebook,
            UnifiedCatalogSchema,
        )

        query = db.query(UnifiedCatalogNotebook)
        workspace = getattr(request.state, "workspace", None)
        if workspace:
            catalog_ids = db.query(CatalogWorkspaceBinding.catalog_id).filter(
                CatalogWorkspaceBinding.workspace_id == workspace.workspace_id,
            )
            query = query.filter(
                UnifiedCatalogNotebook.schema.has(
                    UnifiedCatalogSchema.catalog_id.in_(catalog_ids)
                )
            )
        records = query.order_by(
            UnifiedCatalogNotebook.catalog_name,
            UnifiedCatalogNotebook.schema_name,
            UnifiedCatalogNotebook.name,
        ).all()

        # The workspace binding above narrows this to catalogs bound to the
        # workspace, which is not the same as what this caller may see.
        records = guard.filter(
            Privilege.BROWSE,
            records,
            lambda n: Securable.notebook(n.catalog_name, n.schema_name, n.name),
        )
        workspace_id = workspace.workspace_id if workspace else None
        return {
            "notebooks": [
                {
                    "id": notebook.id,
                    "path": notebook.blob_path,
                    "name": notebook.name,
                    "full_name": notebook.full_name,
                    "catalog_name": notebook.catalog_name,
                    "schema_name": notebook.schema_name,
                    "storage_location": _catalog_storage_location(db, notebook, workspace_id),
                    "last_compute_resource_id": notebook.last_compute_resource_id,
                    "last_kernel_name": notebook.last_kernel_name,
                }
                for notebook in records
            ]
        }


def list_notebooks(request, db, guard):
    return ListNotebooks().execute(request, db, guard)
