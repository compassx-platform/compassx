from fastapi import Request

from app.compute.shared.support import _caller, _error, _require_compute, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege


class StopComputeResource:
    def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        try:
            service = _service(req_context, db)
            service.stop_resource(resource_id, user_id, workspace_id=workspace_id)
            return {"stopped": True, "resource_id": resource_id}
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)
        except Exception as exc:
            logger.exception("Error stopping compute resource")
            return _error("InternalError", str(exc), 500)


def stop_compute_resource(req_context, resource_id, db, guard):
    return StopComputeResource().execute(req_context, resource_id, db, guard)
