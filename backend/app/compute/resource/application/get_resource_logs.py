from fastapi import Request

from app.compute.shared.support import (
    EventSourceResponse,
    _SSE_AVAILABLE,
    _caller,
    _error,
    _require_compute,
    _service,
)
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from compute.config import compute_settings
from compute.logs import stream_pod_logs


class GetResourceLogs:
    async def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        try:
            service = _service(req_context, db)
            resource = service.get_resource_with_status(resource_id, user_id, workspace_id=workspace_id)
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)

        if not _SSE_AVAILABLE:
            return _error("NotSupported", "sse-starlette not installed", 501)

        if service.runtime_manager is not None and service._use_platform():
            if resource.phase not in ("Running", "Pending"):
                return _error(
                    "RuntimeNotRunning", f"No running runtime for resource: {resource_id}", 400
                )
            rm = service.runtime_manager

            async def platform_log_generator():
                from compassx.models import RuntimeNotFoundError

                try:
                    async for line in rm.stream_logs(resource_id):
                        yield {"data": line}
                except RuntimeNotFoundError:
                    yield {"data": f"[info] Compute runtime {resource_id} is initializing. Logs will appear once the container starts."}

            return EventSourceResponse(platform_log_generator())

        if not resource.pod_name:
            return _error("PodNotRunning", f"No running pod for resource: {resource_id}", 400)

        async def log_generator():
            async for line in stream_pod_logs(
                pod_name=resource.pod_name,
                namespace=compute_settings.COMPASSX_NAMESPACE,
            ):
                yield {"data": line}

        return EventSourceResponse(log_generator())


def get_resource_logs(req_context, resource_id, db, guard):
    return GetResourceLogs().execute(req_context, resource_id, db, guard)
