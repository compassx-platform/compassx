from fastapi import Request

from app.compute.shared.support import _caller, _error, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable


class ListComputeResources:
    def execute(self, req_context: Request, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        try:
            service = _service(req_context, db)
            resources = service.list_resources_with_status(user_id, workspace_id=workspace_id)
        except Exception as exc:
            logger.exception("Error listing compute resources")
            return _error("InternalError", str(exc), 500)

        return [
            r
            for r in resources
            if r.is_default or guard.can(Privilege.BROWSE, Securable.compute(r.id))
        ]


def list_compute_resources(req_context, db, guard):
    return ListComputeResources().execute(req_context, db, guard)
