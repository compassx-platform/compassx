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
from app.services.sandbox_reaper_service import unified_reaper_service
from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from compute.manager import JobNotFoundError


class GetKernelInfo:
    def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        from kubernetes import stream as k8s_stream
        from kubernetes.client.exceptions import ApiException

        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        service = _service(req_context, db)
        unified_reaper_service.touch_compute_activity(resource_id)
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
                f"Compute pod for resource {resource_id} is {status_phase}. Wait for it to be Running before connecting.",
                400,
            )

        if service._use_platform():
            catalog_api_url = _kernel_catalog_api_url()
            kernelspec_map = {"spark": "spark_python", "ray": "ray_python", "flink": "flink_python", "duckdb": "duckdb_python"}
            return {
                "resource_id": resource_id,
                "job_id": job_id,
                "pod_name": None,
                "pod_ip": None,
                "runtime": resource.runtime,
                "phase": status_phase,
                "kernel_ready": False,
                "kernel_env": {
                    "COMPASSX_JOB_ID": job_id,
                    "KERNEL_RUNTIME": resource.runtime,
                    "KERNEL_CATALOG_API_URL": catalog_api_url,
                    "CATALOG_API_URL": catalog_api_url,
                },
                "kernelspec_name": kernelspec_map.get(resource.runtime, "spark_python"),
            }
        k8s = get_k8s_client()
        namespace = compute_settings.COMPASSX_NAMESPACE
        try:
            pod = k8s.core().read_namespaced_pod(name=status.pod_name, namespace=namespace)
            pod_ip = pod.status.pod_ip if pod.status else None
        except ApiException as exc:
            return _error("K8sError", f"Could not read pod: {exc}", 500)

        kernel_ready = False
        try:
            resp = k8s_stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                status.pod_name,
                namespace,
                command=["python", "-c", "import ipykernel; print('ok')"],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=10,
            )
            kernel_ready = "ok" in (resp or "")
        except Exception as exc:
            logger.debug("ipykernel check failed for resource %s: %s", resource_id, exc)

        kernelspec_map = {
            "spark": "spark_python",
            "ray": "ray_python",
            "flink": "flink_python",
            "duckdb": "duckdb_python",
        }

        catalog_api_url = _kernel_catalog_api_url()

        return {
            "resource_id": resource_id,
            "job_id": job_id,
            "pod_name": status.pod_name,
            "pod_ip": pod_ip,
            "runtime": resource.runtime,
            "phase": status.phase,
            "kernel_ready": kernel_ready,
            "kernel_env": {
                "COMPASSX_JOB_ID": job_id,
                "KERNEL_RUNTIME": resource.runtime,
                "KERNEL_CATALOG_API_URL": catalog_api_url,
            },
            "kernelspec_name": kernelspec_map.get(resource.runtime, "spark_python"),
        }


def get_kernel_info(req_context, resource_id, db, guard):
    return GetKernelInfo().execute(req_context, resource_id, db, guard)
