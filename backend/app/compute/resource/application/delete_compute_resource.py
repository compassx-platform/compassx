from fastapi import Request

from app.compute.shared.support import _caller, _error, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable


class DeleteComputeResource:
    def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        guard.require(Privilege.MANAGE, Securable.compute(resource_id))
        try:
            service = _service(req_context, db)
            service.delete_resource(resource_id, user_id, workspace_id=workspace_id)
            return {"deleted": True, "resource_id": resource_id}
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)
        except Exception as exc:
            logger.exception("Error deleting compute resource")
            return _error("InternalError", str(exc), 500)


def delete_compute_resource(req_context, resource_id, db, guard):
    return DeleteComputeResource().execute(req_context, resource_id, db, guard)
