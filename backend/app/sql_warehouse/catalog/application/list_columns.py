from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI


class ListColumns:
    async def execute(self, request: Request, catalog: str, schema: str, table: str, db: Session, user):
        del user
        workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
        return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_columns(catalog, schema, table)


def list_columns(request, catalog, schema, table, db, user):
    return ListColumns().execute(request, catalog, schema, table, db, user)
