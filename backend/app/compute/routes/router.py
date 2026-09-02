"""FastAPI router for the compute module.

Prefix /api/v1/compute is applied in main.py.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, wait

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.database import get_account_db, get_system_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from compute.config import compute_settings
from compassx.lookup import try_resolve_url_container
from compute.k8s_client import get_k8s_client
from compute.logs import stream_pod_logs
from compute.manager import ComputeManager, JobNotFoundError, get_compute_manager
from compute.profiles import get_available_profiles
from compute.resource_service import ComputeResourceService
from compute.schemas import (
    ComputeProfileInfo,
    ComputeResourceRequest,
    ComputeResourceResponse,
    ComputeResourceStatus,
    ComputeServiceInfo,
)
from services.airflow.manager import get_airflow_manager
from services.base import ServicePhase, ServiceStatus
from services.enterprise_gateway.manager import get_eg_manager
from services.minio.manager import get_minio_manager

try:
    from sse_starlette.sse import EventSourceResponse

    _SSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SSE_AVAILABLE = False

router = APIRouter(tags=["compute"])

logger = logging.getLogger(__name__)
_STATUS_TIMEOUT_SECONDS = 3


def _kernel_catalog_api_url() -> str:
    """Return a catalog URL that notebook kernels can reach from containers/pods."""
    return try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"


def _service(req_context: Request, db) -> "ComputeResourceService":
    """Build the resource service with the platform RuntimeManager injected."""
    from app.compute.services.resource_service import platform_enabled
    from app.dependencies import get_runtime_manager

    runtime_manager = None
    if platform_enabled():
        try:
            runtime_manager = get_runtime_manager(req_context)
        except Exception:
            logger.exception("Platform runtime manager unavailable; using legacy path")
    return ComputeResourceService(db, runtime_manager=runtime_manager)


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


def _caller(req_context: Request, guard: Guard) -> tuple[str, str]:
    """The (user_id, workspace_id) a compute request acts as.

    Both come from the resolved workspace context. These used to arrive as
    ``user_id`` query parameters, which meant any caller could name any user
    and operate as them; the resource service scopes its lookups by that id,
    so supplying someone else's was enough to list, start, and delete their
    resources.
    """
    ctx = getattr(req_context.state, "workspace", None)
    if ctx is None:
        raise HTTPException(
            status_code=400,
            detail="No workspace context. Address this endpoint under /w/<workspace>.",
        )
    return str(guard.principal.id), str(ctx.workspace_id)


def _require_compute(guard: Guard, db, resource_id: str, privilege: Privilege) -> None:
    """Enforce ``privilege`` on a compute resource, excepting the default.

    Every workspace is provisioned with one ``is_default`` compute resource
    (see ``ensure_workspace_default_resources``), and it is what a notebook
    attaches to when the user has not chosen anything. Requiring a grant on it
    would mean no member could open a notebook until an admin granted
    USE_COMPUTE one principal at a time — so the default is attachable by any
    member of the workspace, which is what "default" already implied.

    The exception covers attaching only. MANAGE on the default still needs a
    real grant, so an ordinary member cannot delete the resource the whole
    workspace depends on.
    """
    securable = Securable.compute(resource_id)
    if privilege in (Privilege.BROWSE, Privilege.USE_COMPUTE) and _is_default_compute(
        db, resource_id
    ):
        return
    guard.require(privilege, securable)


def _is_default_compute(db, resource_id: str) -> bool:
    from app.models.compute_resources import ComputeResource

    return bool(
        db.query(ComputeResource.id)
        .filter(
            ComputeResource.id == resource_id,
            ComputeResource.is_default.is_(True),
        )
        .first()
    )


#: Applied to the endpoints that report infrastructure state rather than a
#: governed object. There is no securable to check — a profile list or a
#: cluster health probe belongs to no one — but the answers describe the
#: deployment's shape, so they are for members of a workspace rather than for
#: anyone who can reach the port. Depending on ``get_guard`` is the check:
#: it raises 401 without an identity and 400 without a workspace.
_WORKSPACE_MEMBER = [Depends(get_guard)]


@router.get(
    "/profiles",
    response_model=list[ComputeProfileInfo],
    dependencies=_WORKSPACE_MEMBER,
)
def list_profiles(env: str = Query(default=None)):
    """Return all compute profiles for the current (or specified) environment."""
    target_env = env or compute_settings.COMPASSX_ENV
    profiles = get_available_profiles(target_env)
    return [
        ComputeProfileInfo(
            id=profile.id,
            label=profile.label,
            description=profile.description,
            available=profile.available,
            reason=profile.unavailable_reason,
            resources={"requests": profile.requests, "limits": profile.limits},
        )
        for profile in profiles
    ]


@router.get("/health", dependencies=_WORKSPACE_MEMBER)
def health_check():
    """Check Kubernetes connectivity."""
    def check_kubernetes() -> None:
        k8s = get_k8s_client()
        ns = compute_settings.COMPASSX_NAMESPACE or "compassx"
        try:
            k8s.core().list_namespaced_pod(namespace=ns, limit=1, _request_timeout=_STATUS_TIMEOUT_SECONDS)
        except Exception:
            k8s.core().get_api_resources(_request_timeout=_STATUS_TIMEOUT_SECONDS)

    try:
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            executor.submit(check_kubernetes).result(timeout=_STATUS_TIMEOUT_SECONDS)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        logger.debug("K8s: health check passed")
        return {"status": "ok", "kubernetes": "reachable"}
    except FutureTimeoutError:
        logger.warning("K8s: health check timed out")
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "kubernetes": "unreachable",
                "message": "Kubernetes health check timed out.",
            },
        )
    except Exception as exc:
        logger.warning("K8s: health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "kubernetes": "unreachable",
                "message": "Kubernetes not reachable." if compute_settings.is_k8s() else "Kubernetes not connected. Start minikube.",
            },
        )



@router.get("/runtime", dependencies=_WORKSPACE_MEMBER)
def runtime_info(req_context: Request):
    """Return the active platform profile and backend service URL."""
    from compassx.lookup import try_resolve_url

    backend_url = try_resolve_url("backend", "http://localhost:8000")
    profile_name = "unknown"
    try:
        platform = getattr(req_context.app.state, "platform", None)
        if platform:
            profile_name = platform.profile.name
    except Exception:
        pass
    return {
        "profile": profile_name,
        "backend_url": backend_url,
        "compassx_env": compute_settings.COMPASSX_ENV,
    }

def _service_info(service_id: str, label: str, status) -> ComputeServiceInfo:
    return ComputeServiceInfo(
        id=service_id,
        label=label,
        phase=status.phase.value if hasattr(status.phase, "value") else str(status.phase),
        message=status.message,
        details=status.details,
    )


def _run_service_action_async(service_name: str, action: str, label: str, manager) -> None:
    logger.info("compute-service: %s %s requested", service_name, action)
    try:
        status = getattr(manager, action)()
        logger.info(
            "compute-service: %s %s completed phase=%s message=%s",
            service_name,
            action,
            status.phase.value if hasattr(status.phase, "value") else str(status.phase),
            status.message,
        )
    except Exception:
        logger.exception("compute-service: %s %s failed", service_name, action)


@router.get(
    "/services",
    response_model=list[ComputeServiceInfo],
    dependencies=_WORKSPACE_MEMBER,
)
def list_compute_services():
    """Return service status for compute dependencies."""
    services = [
        ("minio", "MinIO", get_minio_manager().get_status),
        ("enterprise-gateway", "Enterprise Gateway", get_eg_manager().get_status),
        ("airflow", "Airflow", get_airflow_manager().get_status),
    ]

    executor = ThreadPoolExecutor(max_workers=len(services))
    try:
        futures = {
            executor.submit(status_fn): (service_id, label)
            for service_id, label, status_fn in services
        }
        done, pending = wait(futures, timeout=_STATUS_TIMEOUT_SECONDS)
        results = []

        for future in done:
            service_id, label = futures[future]
            try:
                status = future.result()
                results.append(_service_info(service_id, label, status))
            except Exception as exc:
                logger.warning("compute-service: %s status failed: %s", service_id, exc)
                results.append(
                    _service_info(
                        service_id,
                        label,
                        ServiceStatus(
                            phase=ServicePhase.ERROR,
                            message=f"{label} status check failed.",
                            details={"error": str(exc)},
                        ),
                    )
                )

        for future in pending:
            service_id, label = futures[future]
            logger.warning("compute-service: %s status timed out", service_id)
            results.append(
                _service_info(
                    service_id,
                    label,
                    ServiceStatus(
                        phase=ServicePhase.ERROR,
                        message=f"{label} status check timed out.",
                        details={"timeout_seconds": _STATUS_TIMEOUT_SECONDS},
                    ),
                )
            )

        return results
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


@router.get("/services/port-forwards/status", dependencies=_WORKSPACE_MEMBER)
def port_forward_status():
    """Port-forward lifecycle is now managed by the compassx CLI launcher."""
    return {
        "enabled": False,
        "message": "Port-forwards are managed by the compassx CLI. Run: compassx status",
        "forwards": [],
    }


@router.post("/services/port-forwards/recover", dependencies=_WORKSPACE_MEMBER)
async def recover_port_forwards():
    """Port-forward lifecycle is now managed by the compassx CLI launcher."""
    return {
        "enabled": False,
        "message": "Port-forwards are managed by the compassx CLI. Run: compassx up",
    }


@router.post("/services/{service_name}/{action}", response_model=ComputeServiceInfo)
def control_compute_service(
    service_name: str,
    action: str,
    guard: Guard = Depends(get_guard),
):
    """Start, stop, or restart a compute service."""
    # MinIO, Enterprise Gateway, and Airflow are shared by the whole
    # deployment; restarting one interrupts every workspace at once. There is
    # no securable to grant on, so this sits with the workspace admin.
    guard.require_workspace_admin(f"Controlling the {service_name} service")

    managers = {
        "minio": ("MinIO", get_minio_manager()),
        "enterprise-gateway": ("Enterprise Gateway", get_eg_manager()),
        "airflow": ("Airflow", get_airflow_manager()),
    }
    actions = {"start", "stop", "restart"}

    if service_name not in managers:
        raise HTTPException(status_code=404, detail=f"Unknown compute service: {service_name}")
    if action not in actions:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    label, manager = managers[service_name]
    if service_name == "airflow":
        thread = threading.Thread(
            target=_run_service_action_async,
            args=(service_name, action, label, manager),
            daemon=True,
        )
        thread.start()
        return _service_info(
            service_name,
            label,
            ServiceStatus(
                phase=ServicePhase.STARTING,
                message=f"{label} {action} requested.",
                details=manager.get_status().details,
            ),
        )

    status = getattr(manager, action)()
    if service_name == "minio" and action in {"start", "restart"}:
        try:
            manager.ensure_buckets()
        except Exception as exc:
            logger.warning("MinIO buckets ensure failed after %s: %s", action, exc)
    return _service_info(service_name, label, status)


# def get_db():
#     """Dependency for database session."""
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


@router.post("/resources", response_model=ComputeResourceResponse, status_code=201)
def create_compute_resource(
    req_context: Request,
    body: ComputeResourceRequest,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new compute resource configuration."""
    user_id, workspace_id = _caller(req_context, guard)
    # A compute resource has no parent securable to hold CREATE on, and each
    # one reserves cluster capacity, so creation sits with the workspace
    # admin rather than being open to every member.
    guard.require_workspace_admin("Creating a compute resource")
    try:
        service = _service(req_context, db)
        resource = service.create_resource(
            body, user_id, user_id, workspace_id=workspace_id
        )
    except ValueError as exc:
        return _error("InvalidRequest", str(exc), 400)
    except Exception as exc:
        logger.exception("Error creating compute resource")
        return _error("InternalError", str(exc), 500)

    guard.claim_ownership(Securable.compute(resource.id))
    return resource


@router.get("/resources", response_model=list[ComputeResourceStatus])
def list_compute_resources(
    req_context: Request,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List the compute resources in this workspace the caller may see."""
    user_id, workspace_id = _caller(req_context, guard)
    try:
        service = _service(req_context, db)
        resources = service.list_resources_with_status(user_id, workspace_id=workspace_id)
    except Exception as exc:
        logger.exception("Error listing compute resources")
        return _error("InternalError", str(exc), 500)

    # The service scopes by workspace, which is not the same as what this
    # caller may see: resources created by other members are in the same
    # workspace but are not necessarily theirs to browse. The workspace
    # default is always listed — see _require_compute.
    return [
        r
        for r in resources
        if r.is_default or guard.can(Privilege.BROWSE, Securable.compute(r.id))
    ]


@router.get("/resources/{resource_id}", response_model=ComputeResourceStatus)
def get_compute_resource_status(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get a compute resource with current pod status if running."""
    user_id, workspace_id = _caller(req_context, guard)
    _require_compute(guard, db, resource_id, Privilege.BROWSE)
    try:
        service = _service(req_context, db)
        return service.get_resource_with_status(resource_id, user_id, workspace_id=workspace_id)
    except ValueError as exc:
        return _error("NotFound", str(exc), 404)
    except Exception as exc:
        logger.exception("Error getting compute resource")
        return _error("InternalError", str(exc), 500)


@router.delete("/resources/{resource_id}")
def delete_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a compute resource configuration."""
    user_id, workspace_id = _caller(req_context, guard)
    # Destroys a resource other notebooks may be attached to, so MANAGE
    # rather than USE_COMPUTE — being allowed to run on something is not
    # permission to take it away from everyone else.
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


@router.post("/resources/{resource_id}/start", response_model=dict, status_code=201)
def start_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start a pod from a compute resource configuration."""
    user_id, workspace_id = _caller(req_context, guard)
    _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
    try:
        service = _service(req_context, db)
        return service.start_resource(resource_id, user_id, workspace_id=workspace_id)
    except ValueError as exc:
        return _error("NotFound", str(exc), 404)
    except Exception as exc:
        logger.exception("Error starting compute resource")
        return _error("InternalError", str(exc), 500)


@router.post("/resources/{resource_id}/stop")
def stop_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop the running pod for a compute resource."""
    user_id, workspace_id = _caller(req_context, guard)
    # Stopping kills every kernel attached to the pod, including other
    # people's. USE_COMPUTE is the right bar because anyone entitled to run
    # here is equally exposed to the restart, and shared resources need to be
    # recoverable without an admin.
    _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
    try:
        service = _service(req_context, db)
        service.stop_resource_pod(resource_id, user_id, workspace_id=workspace_id)
        return {"stopped": True, "resource_id": resource_id}
    except ValueError as exc:
        return _error("NotFound", str(exc), 404)
    except Exception as exc:
        logger.exception("Error stopping compute resource")
        return _error("InternalError", str(exc), 500)


@router.get("/resources/{resource_id}/logs")
async def get_resource_logs(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stream pod logs for the running pod owned by a compute resource."""
    user_id, workspace_id = _caller(req_context, guard)
    # Pod logs carry whatever the workloads on it printed — query text, row
    # samples, stack traces with data in them. That is the content of the
    # work running there, not just its existence, so USE_COMPUTE rather than
    # BROWSE.
    _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
    try:
        service = _service(req_context, db)
        resource = service.get_resource_with_status(resource_id, user_id, workspace_id=workspace_id)
    except ValueError as exc:
        return _error("NotFound", str(exc), 404)

    if not _SSE_AVAILABLE:
        return _error("NotSupported", "sse-starlette not installed", 501)

    # Platform path: driver-agnostic log streaming keyed by runtime ID.
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
                yield {"data": f"[error] Runtime not found: {resource_id}"}

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


@router.get("/resources/{resource_id}/kernel-info")
def get_kernel_info(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Return notebook kernel connection info for a running compute resource."""
    from kubernetes import stream as k8s_stream
    from kubernetes.client.exceptions import ApiException

    user_id, workspace_id = _caller(req_context, guard)
    # The response is a connection recipe — pod IP, kernelspec, and the env a
    # kernel is launched with. Anyone holding it can attach to the pod, so it
    # takes the same privilege as running there.
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


@router.post("/resources/{resource_id}/start-kernel")
def start_kernel_for_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start an EG kernel for the running pod owned by a compute resource."""
    import httpx
    from services.enterprise_gateway.config import eg_settings

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
                },
            },
            timeout=float(eg_settings.EG_KERNEL_LAUNCH_TIMEOUT),
        )
        resp.raise_for_status()
        return resp.json()
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



