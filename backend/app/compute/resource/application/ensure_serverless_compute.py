from fastapi import Request

from app.compute.shared.support import _caller, _error, _service, logger
from app.governance.dependencies import Guard


class EnsureServerlessCompute:
    def execute(self, req_context: Request, body, notebook_id, notebook_name, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        effective_notebook_id = (body and body.notebook_id) or notebook_id
        effective_notebook_name = (body and body.notebook_name) or notebook_name
        try:
            service = _service(req_context, db)
            return service.ensure_serverless_resource(
                user_id,
                workspace_id=workspace_id,
                created_by=user_id,
                notebook_id=effective_notebook_id,
                notebook_name=effective_notebook_name,
            )
        except Exception as exc:
            logger.exception("Error ensuring serverless compute resource")
            return _error("InternalError", str(exc), 500)


def ensure_serverless_compute(req_context, body, notebook_id, notebook_name, db, guard):
    return EnsureServerlessCompute().execute(req_context, body, notebook_id, notebook_name, db, guard)
