import re

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.notebooks.shared.support import _catalog_storage_location


class CreateNotebook:
    async def execute(self, body, request: Request, db: Session, user: dict, guard: Guard):
        from app.catalog.models import (
            CatalogWorkspaceBinding,
            UnifiedCatalog,
            UnifiedCatalogSchema,
        )
        from app.catalog.schemas import NotebookCreate
        from app.catalog.service import create_notebook as create_catalog_notebook

        catalog_name = body.catalog_name
        schema_name = body.schema_name
        if not catalog_name or not schema_name:
            workspace = getattr(request.state, "workspace", None)
            if not workspace:
                raise HTTPException(
                    status_code=422,
                    detail="catalog_name and schema_name are required outside a workspace.",
                )
            binding = db.query(CatalogWorkspaceBinding).filter(
                CatalogWorkspaceBinding.workspace_id == workspace.workspace_id,
            ).order_by(CatalogWorkspaceBinding.is_default.desc()).first()
            catalog = db.query(UnifiedCatalog).filter(
                UnifiedCatalog.id == binding.catalog_id
            ).first() if binding else None
            schema = db.query(UnifiedCatalogSchema).filter(
                UnifiedCatalogSchema.catalog_id == catalog.id
            ).order_by(UnifiedCatalogSchema.name).first() if catalog else None
            if not catalog or not schema:
                raise HTTPException(
                    status_code=422,
                    detail="The workspace has no bound catalog schema for notebooks.",
                )
            catalog_name, schema_name = catalog.name, schema.name

        # Checked after the fallback above resolves a schema, because the caller
        # may not have named one — the workspace's default binding did.
        guard.require(Privilege.CREATE, Securable.schema_(catalog_name, schema_name))

        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", body.name.strip()).strip("_") or "untitled"
        try:
            notebook = await create_catalog_notebook(
                db,
                catalog_name,
                schema_name,
                NotebookCreate(name=safe_name),
                user,
            )
        except ValueError as exc:
            status = 409 if "already exists" in str(exc) else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        guard.claim_ownership(
            Securable.notebook(catalog_name, schema_name, notebook.name)
        )
        return {
            "id": notebook.id,
            "path": notebook.blob_path,
            "name": notebook.name,
            "full_name": notebook.full_name,
            "catalog_name": notebook.catalog_name,
            "schema_name": notebook.schema_name,
            "storage_location": _catalog_storage_location(
                db,
                notebook,
                getattr(getattr(request.state, "workspace", None), "workspace_id", None),
            ),
        }


def create_notebook(body, request, db, user, guard):
    return CreateNotebook().execute(body, request, db, user, guard)
