from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.notebooks.shared.support import _authorized_notebook


class SaveNotebook:
    async def execute(self, path: str, request_body: dict, db: Session, guard: Guard):
        from app.catalog.models import UnifiedCatalogSchema
        notebook = _authorized_notebook(db, guard, path, Privilege.EDIT)
        schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
        from app.catalog.service import _write_notebook_content
        await _write_notebook_content(db, schema, notebook.blob_path, request_body)
        return {"saved": True, "path": path}


def save_notebook(path, request_body, db, guard):
    return SaveNotebook().execute(path, request_body, db, guard)
