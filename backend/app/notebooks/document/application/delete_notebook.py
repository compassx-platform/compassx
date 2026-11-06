from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.notebooks.shared.support import _authorized_notebook


class DeleteNotebook:
    async def execute(self, path: str, db: Session, guard: Guard):
        from app.catalog.models import UnifiedCatalogSchema
        notebook = _authorized_notebook(db, guard, path, Privilege.MANAGE)
        schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
        from app.catalog.service import _delete_notebook_file
        await _delete_notebook_file(db, schema, notebook.blob_path)
        db.delete(notebook)
        db.commit()
        return {"deleted": True, "path": path}


def delete_notebook(path, db, guard):
    return DeleteNotebook().execute(path, db, guard)
