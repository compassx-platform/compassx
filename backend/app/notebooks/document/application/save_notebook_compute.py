from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable


class SaveNotebookCompute:
    def execute(self, notebook_id: str, body, db: Session, guard: Guard):
        from app.catalog.models import UnifiedCatalogNotebook

        notebook = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.id == notebook_id
        ).first()
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # This writes to the notebook record, so it takes EDIT — and it also
        # points the notebook at a compute resource, so the caller must be
        # entitled to run things there.
        guard.require(
            Privilege.EDIT,
            Securable.notebook(
                notebook.catalog_name, notebook.schema_name, notebook.name
            ),
        )
        guard.require(Privilege.USE_COMPUTE, Securable.compute(body.resource_id))

        notebook.last_compute_resource_id = body.resource_id
        notebook.last_kernel_name = body.kernel_name
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save compute info: {exc}") from exc
        return {"saved": True, "notebook_id": notebook_id}


def save_notebook_compute(notebook_id, body, db, guard):
    return SaveNotebookCompute().execute(notebook_id, body, db, guard)
