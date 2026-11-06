from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI


class ListTables:
    async def execute(self, request: Request, catalog: str, schema: str, db: Session, user):
        del user
        workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
        return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_tables(catalog, schema)


def list_tables(request, catalog, schema, db, user):
    return ListTables().execute(request, catalog, schema, db, user)
