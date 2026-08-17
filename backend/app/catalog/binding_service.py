from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.catalog.models import UnifiedCatalog, CatalogWorkspaceBinding
from app.catalog.schemas import BindingCreate, CatalogPrivilege


class CatalogBindingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def bind_catalog(
        self,
        workspace_id: str,
        data: BindingCreate,
        bound_by: str = "system",
    ) -> CatalogWorkspaceBinding:
        # Find catalog by name
        catalog = self.db.query(UnifiedCatalog).filter(UnifiedCatalog.name == data.catalog_name).first()
        if not catalog:
            # If the default catalog, ensure it exists
            if data.catalog_name == "compassx":
                from app.catalog.service import ensure_default_catalog
                catalog = ensure_default_catalog(self.db, created_by=bound_by)
            else:
                raise ValueError(f"Catalog '{data.catalog_name}' not found")

        # Check if already bound
        existing = (
            self.db.query(CatalogWorkspaceBinding)
            .filter(
                CatalogWorkspaceBinding.catalog_id == catalog.id,
                CatalogWorkspaceBinding.workspace_id == workspace_id,
            )
            .first()
        )
        if existing:
            existing.privilege = data.privilege.value
            existing.is_default = data.is_default
            existing.bound_by = bound_by
            existing.bound_at = func.now()
            # If this is marked default, unset is_default on other bindings for this workspace
            if data.is_default:
                self.db.query(CatalogWorkspaceBinding).filter(
                    CatalogWorkspaceBinding.workspace_id == workspace_id,
                    CatalogWorkspaceBinding.catalog_id != catalog.id,
                ).update({"is_default": False})
            return existing

        binding = CatalogWorkspaceBinding(
            catalog_id=catalog.id,
            workspace_id=workspace_id,
            privilege=data.privilege.value,
            is_default=data.is_default,
            bound_by=bound_by,
        )
        self.db.add(binding)
        # If this is marked default, unset is_default on other bindings for this workspace
        if data.is_default:
            self.db.query(CatalogWorkspaceBinding).filter(
                CatalogWorkspaceBinding.workspace_id == workspace_id,
                CatalogWorkspaceBinding.catalog_id != catalog.id,
            ).update({"is_default": False})

        return binding

    def get_bindings(self, catalog_name: str) -> dict:
        catalog = self.db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found")

        from app.workspace.models import Workspace

        bindings_query = (
            self.db.query(CatalogWorkspaceBinding, Workspace.name, Workspace.slug)
            .join(Workspace, CatalogWorkspaceBinding.workspace_id == Workspace.id)
            .filter(CatalogWorkspaceBinding.catalog_id == catalog.id)
            .all()
        )

        return {
            "all_workspaces": catalog.all_workspaces,
            "bindings": [
                {
                    "id": b.id,
                    "catalog_id": b.catalog_id,
                    "workspace_id": b.workspace_id,
                    "workspace_name": name,
                    "workspace_slug": slug,
                    "privilege": b.privilege,
                    "is_default": b.is_default,
                    "bound_by": b.bound_by,
                    "bound_at": b.bound_at,
                }
                for b, name, slug in bindings_query
            ]
        }

    def update_bindings(self, catalog_name: str, all_workspaces: bool, workspace_ids: list[str], bound_by: str = "admin") -> None:
        catalog = self.db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found")

        catalog.all_workspaces = all_workspaces

        # Delete all existing bindings for this catalog
        self.db.query(CatalogWorkspaceBinding).filter(
            CatalogWorkspaceBinding.catalog_id == catalog.id
        ).delete()

        # If not all_workspaces, insert bindings for the specified workspace_ids
        if not all_workspaces:
            for ws_id in workspace_ids:
                binding = CatalogWorkspaceBinding(
                    catalog_id=catalog.id,
                    workspace_id=ws_id,
                    privilege=CatalogPrivilege.READ_WRITE.value,
                    is_default=False,
                    bound_by=bound_by,
                )
                self.db.add(binding)

        self.db.commit()
