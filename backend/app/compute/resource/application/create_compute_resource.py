from fastapi import Request

from app.compute.shared.support import _caller, _error, _service, logger
from app.governance.dependencies import Guard
from app.governance.securable import Securable


class CreateComputeResource:
    def execute(self, req_context: Request, body, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        ctx = getattr(req_context.state, "workspace", None)
        workspace_name = (ctx.workspace_slug or ctx.workspace_name) if ctx else None
        guard.require_workspace_admin("Creating a compute resource")
        try:
            service = _service(req_context, db)
            resource = service.create_resource(
                body,
                user_id,
                user_id,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
            )
        except ValueError as exc:
            return _error("InvalidRequest", str(exc), 400)
        except Exception as exc:
            logger.exception("Error creating compute resource")
            return _error("InternalError", str(exc), 500)

        guard.claim_ownership(Securable.compute(resource.id))
        return resource


def create_compute_resource(req_context, body, db, guard):
    return CreateComputeResource().execute(req_context, body, db, guard)
