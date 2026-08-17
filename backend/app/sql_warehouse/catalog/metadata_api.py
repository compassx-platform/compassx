from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import service as catalog_service
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTable


class CatalogMetadataAPI:
    def __init__(self, db: Session, workspace_id: str | None = None):
        self.db = db
        self.workspace_id = workspace_id

    def _catalog(self, name: str) -> UnifiedCatalog | None:
        stmt = select(UnifiedCatalog)
        if self.workspace_id:
            from app.catalog.models import CatalogWorkspaceBinding
            stmt = stmt.outerjoin(CatalogWorkspaceBinding).where(
                (UnifiedCatalog.all_workspaces == True) |
                (CatalogWorkspaceBinding.workspace_id == self.workspace_id)
            )
        catalog = self.db.scalar(stmt.where(UnifiedCatalog.name == name))
        if catalog is None and name == "default":
            catalog = self.db.scalar(stmt.order_by(UnifiedCatalog.name))
        return catalog

    async def list_catalogs(self) -> dict:
        stmt = select(UnifiedCatalog).order_by(UnifiedCatalog.name)
        if self.workspace_id:
            from app.catalog.models import CatalogWorkspaceBinding
            stmt = stmt.outerjoin(CatalogWorkspaceBinding).where(
                (UnifiedCatalog.all_workspaces == True) |
                (CatalogWorkspaceBinding.workspace_id == self.workspace_id)
            )
        catalogs = self.db.scalars(stmt).all()
        return {
            "catalogs": [
                {"name": item.name, "catalog_type": item.catalog_type or "managed"}
                for item in catalogs
            ]
        }

    async def list_schemas(self, catalog: str = "default") -> dict:
        item = self._catalog(catalog)
        if item is None:
            return {"schemas": []}
        if item.catalog_type == "postgres" and item.connection_id and item.database_name:
            schemas = catalog_service.browse_connection_schemas(
                self.db, item.connection_id, item.database_name
            )
            return {"schemas": [schema.name for schema in schemas]}
        schemas = self.db.scalars(
            select(UnifiedCatalogSchema)
            .where(UnifiedCatalogSchema.catalog_id == item.id)
            .order_by(UnifiedCatalogSchema.name)
        ).all()
        return {"schemas": [schema.name for schema in schemas]}

    async def list_tables(self, catalog: str = "default", schema: str = "public") -> dict:
        item = self._catalog(catalog)
        if item is None:
            return {"tables": []}
        if item.catalog_type == "postgres" and item.connection_id and item.database_name:
            tables = catalog_service.browse_connection_tables(
                self.db, item.connection_id, item.database_name, schema
            )
            return {"tables": [table.name for table in tables]}
        tables = catalog_service.list_tables(self.db, item.name, schema)
        return {"tables": [table.name for table in tables]}

    async def list_columns(self, catalog: str = "default", schema: str = "public", table: str = "") -> dict:
        item = self._catalog(catalog)
        if item is None:
            return {"columns": []}
        model = self.db.scalar(
            select(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema)
            .where(
                UnifiedCatalogSchema.catalog_id == item.id,
                UnifiedCatalogSchema.name == schema,
                UnifiedCatalogTable.name == table,
            )
        )
        if model is None:
            return {"columns": []}
        columns = catalog_service.introspect_columns(self.db, model)
        return {
            "columns": [
                {"name": column.name, "type": column.data_type, "nullable": column.nullable}
                for column in columns
            ]
        }
