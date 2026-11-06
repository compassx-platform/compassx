from fastapi import Request

from app.compute.shared.support import _caller, _error, _require_compute, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege


class UpdateComputeResource:
    def execute(self, req_context: Request, resource_id: str, body, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        try:
            service = _service(req_context, db)
            return service.update_resource(
                resource_id,
                body,
                user_id,
                workspace_id=workspace_id,
            )
        except ValueError as exc:
            return _error("InvalidRequest", str(exc), 400)
        except Exception as exc:
            logger.exception("Error updating compute resource")
            return _error("InternalError", str(exc), 500)


def update_compute_resource(req_context, resource_id, body, db, guard):
    return UpdateComputeResource().execute(req_context, resource_id, body, db, guard)
