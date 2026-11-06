import httpx
from fastapi import Request

from app.compute.shared.support import (
    _caller,
    _error,
    _kernel_catalog_api_url,
    _require_compute,
    _service,
    logger,
)
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from compute.manager import JobNotFoundError
from services.enterprise_gateway.config import eg_settings


class StartKernelForResource:
    def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        service = _service(req_context, db)
        try:
            resource = service.get_resource_with_status(resource_id, user_id, workspace_id=workspace_id)
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)

        job_id = resource.job_id
        if not job_id:
            return _error("PodNotRunning", f"No running pod for resource: {resource_id}", 400)

        if service._use_platform():
            status_phase = resource.phase or "Unknown"
            status_pod_name = None
        else:
            try:
                status = service.manager.get_job_status(job_id)
            except JobNotFoundError as exc:
                return _error("JobNotFound", str(exc), 404)
            status_phase = status.phase
            status_pod_name = status.pod_name

        if status_phase != "Running":
            return _error(
                "PodNotRunning",
                f"Compute pod for resource {resource_id} is {status_phase}. Wait for Running state.",
                400,
            )

        kernelspec_map = {
            "spark": "spark_python",
            "ray": "ray_python",
            "flink": "flink_python",
            "duckdb": "duckdb_python",
        }
        kernel_name = kernelspec_map.get(resource.runtime, "duckdb_python")
        eg_url = eg_settings.internal_url()

        try:
            existing = httpx.get(f"{eg_url}/api/kernels", timeout=10)
            if existing.is_success:
                for kernel in existing.json():
                    env = (kernel.get("metadata") or {}).get("env") or {}
                    if env.get("KERNEL_COMPASSX_JOB_ID") == job_id:
                        httpx.delete(f"{eg_url}/api/kernels/{kernel['id']}", timeout=10)
                        logger.info(
                            "start-kernel: killed stale kernel %s for resource %s",
                            kernel["id"],
                            resource_id,
                        )
        except Exception as exc:
            logger.debug("start-kernel: stale kernel cleanup failed (non-fatal): %s", exc)

        auth_header = req_context.headers.get("Authorization", "")
        session_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

        catalog_api_url = _kernel_catalog_api_url()

        ws_id_val = workspace_id
        if not ws_id_val:
            try:
                raw_res = service.get_resource(resource_id)
                if raw_res and getattr(raw_res, "workspace_id", None):
                    ws_id_val = raw_res.workspace_id
            except Exception:
                pass

        ws_id_str = str(ws_id_val) if ws_id_val else ""
        ws_slug_str = ""
        if ws_id_val:
            ws_slug_str = service._resolve_workspace_name(ws_id_val)

        try:
            resp = httpx.post(
                f"{eg_url}/api/kernels",
                json={
                    "name": kernel_name,
                    "env": {
                        "KERNEL_COMPASSX_JOB_ID": job_id,
                        "KERNEL_RUNTIME": resource.runtime,
                        "KERNEL_CATALOG_API_URL": catalog_api_url,
                        "KERNEL_NOTEBOOK_SESSION_TOKEN": session_token,
                        "CATALOG_API_URL": catalog_api_url,
                        "NOTEBOOK_SESSION_TOKEN": session_token,
                        "KERNEL_WORKSPACE_ID": ws_id_str,
                        "WORKSPACE_ID": ws_id_str,
                        "KERNEL_WORKSPACE_SLUG": ws_slug_str,
                        "WORKSPACE_SLUG": ws_slug_str,
                    },
                },
                timeout=float(eg_settings.EG_KERNEL_LAUNCH_TIMEOUT),
            )
            resp.raise_for_status()
            data = resp.json()
            kernel_id = data.get("id")
            if kernel_id:
                try:
                    from app.notebooks.routes.jupyter_proxy import register_kernel_resource
                    register_kernel_resource(kernel_id, resource_id)
                except Exception:
                    pass
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                "EG kernel start failed resource_id=%s status=%s body=%s",
                resource_id,
                exc.response.status_code,
                exc.response.text,
            )
            return _error("EGError", f"EG returned {exc.response.status_code}: {exc.response.text}", 502)
        except httpx.ConnectError as exc:
            logger.warning(
                "EG kernel start failed resource_id=%s url=%s error=%s",
                resource_id,
                eg_url,
                exc,
            )
            return _error(
                "EGUnreachable",
                f"Enterprise Gateway is not reachable at {eg_url}. Start the Enterprise Gateway service or its local port-forward, then retry.",
                503,
            )
        except Exception as exc:
            logger.exception("EG kernel start failed resource_id=%s", resource_id)
            return _error("EGError", str(exc), 500)


def start_kernel_for_resource(req_context, resource_id, db, guard):
    return StartKernelForResource().execute(req_context, resource_id, db, guard)
