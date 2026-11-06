from fastapi import Request

from app.compute.shared.support import _caller, _error, _require_compute, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege


class GetComputeResourceMetrics:
    def execute(self, req_context: Request, resource_id: str, range: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.BROWSE)
        try:
            service = _service(req_context, db)
            return service.get_resource_metrics(
                resource_id, user_id, workspace_id=workspace_id, time_range=range
            )
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)
        except Exception as exc:
            logger.exception("Error fetching compute resource metrics")
            return _error("InternalError", str(exc), 500)


def get_compute_resource_metrics(req_context, resource_id, range, db, guard):
    return GetComputeResourceMetrics().execute(req_context, resource_id, range, db, guard)
