from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI


class ListSchemas:
    async def execute(self, request: Request, catalog: str, db: Session, user):
        del user
        workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
        return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_schemas(catalog)


def list_schemas(request, catalog, db, user):
    return ListSchemas().execute(request, catalog, db, user)
