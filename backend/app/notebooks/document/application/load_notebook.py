from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.notebooks.shared.support import _authorized_notebook


class LoadNotebook:
    async def execute(self, path: str, db: Session, guard: Guard):
        from app.catalog.models import UnifiedCatalogSchema
        # SELECT, not BROWSE: the response is the notebook's full source and
        # stored cell outputs, which routinely contain query results.
        notebook = _authorized_notebook(db, guard, path, Privilege.SELECT)
        schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
        from app.catalog.service import _notebook_exists, _read_notebook_content
        if not await _notebook_exists(db, schema, notebook.blob_path):
            raise HTTPException(status_code=404, detail="Notebook not found")
        content = await _read_notebook_content(db, schema, notebook.blob_path)
        # Inject catalog metadata so frontend can auto-reconnect to last compute and show info
        content["_catalog"] = {
            "id": notebook.id,
            "name": notebook.name,
            "catalog_name": notebook.catalog_name,
            "schema_name": notebook.schema_name,
            "created_at": notebook.created_at.isoformat() if notebook.created_at else None,
            "updated_at": notebook.updated_at.isoformat() if notebook.updated_at else None,
            "created_by": notebook.created_by,
            "updated_by": notebook.updated_by,
            "last_compute_resource_id": notebook.last_compute_resource_id,
            "last_kernel_name": notebook.last_kernel_name,
        }
        return JSONResponse(content=content)


def load_notebook(path, db, guard):
    return LoadNotebook().execute(path, db, guard)
