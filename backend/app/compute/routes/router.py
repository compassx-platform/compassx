"""FastAPI router for the compute module.

Prefix /api/v1/compute is applied in main.py.
Handlers stay here. Each one forwards to one application type.
"""
import logging

from fastapi import APIRouter, Depends, Query, Request

from app.database import SessionLocal
from app.database import get_account_db, get_system_db
from app.governance.dependencies import Guard, get_guard
from app.compute.health.application.health_check import health_check as health_check_action
from app.compute.health.application.runtime_info import runtime_info as runtime_info_action
from app.compute.profile.application.list_profiles import list_profiles as list_profiles_action
from app.compute.resource.application.create_compute_resource import create_compute_resource as create_compute_resource_action
from app.compute.resource.application.delete_compute_resource import delete_compute_resource as delete_compute_resource_action
from app.compute.resource.application.ensure_serverless_compute import ensure_serverless_compute as ensure_serverless_compute_action
from app.compute.resource.application.get_compute_resource_metrics import get_compute_resource_metrics as get_compute_resource_metrics_action
from app.compute.resource.application.get_compute_resource_status import get_compute_resource_status as get_compute_resource_status_action
from app.compute.resource.application.get_kernel_info import get_kernel_info as get_kernel_info_action
from app.compute.resource.application.get_resource_logs import get_resource_logs as get_resource_logs_action
from app.compute.resource.application.list_compute_resources import list_compute_resources as list_compute_resources_action
from app.compute.resource.application.start_compute_resource import start_compute_resource as start_compute_resource_action
from app.compute.resource.application.start_kernel_for_resource import start_kernel_for_resource as start_kernel_for_resource_action
from app.compute.resource.application.stop_compute_resource import stop_compute_resource as stop_compute_resource_action
from app.compute.resource.application.update_compute_resource import update_compute_resource as update_compute_resource_action
from app.compute.service_control.application.control_compute_service import control_compute_service as control_compute_service_action
from app.compute.service_control.application.list_compute_services import list_compute_services as list_compute_services_action
from app.compute.service_control.application.port_forward_status import port_forward_status as port_forward_status_action
from app.compute.service_control.application.recover_port_forwards import recover_port_forwards as recover_port_forwards_action
from app.compute.shared.support import (
    _active_driver,
    _caller,
    _error,
    _is_default_compute,
    _kernel_catalog_api_url,
    _require_compute,
    _service,
    _service_info,
)
from compute.schemas import (
    ComputeMetricsResponse,
    ComputeProfileInfo,
    ComputeResourceRequest,
    ComputeResourceResponse,
    ComputeResourceStatus,
    ComputeResourceUpdateRequest,
    ComputeServiceInfo,
    EnsureServerlessRequest,
)

router = APIRouter(tags=["compute"])
logger = logging.getLogger(__name__)

_WORKSPACE_MEMBER = [Depends(get_guard)]


@router.get(
    "/profiles",
    response_model=list[ComputeProfileInfo],
    dependencies=_WORKSPACE_MEMBER,
)
def list_profiles(env: str = Query(default=None)):
    """Return all compute profiles for the current (or specified) environment."""
    return list_profiles_action(env)


@router.get("/health", dependencies=_WORKSPACE_MEMBER)
def health_check(req_context: Request):
    """Check compute infrastructure connectivity (Docker or Kubernetes depending on active profile)."""
    return health_check_action(req_context)


@router.get("/runtime", dependencies=_WORKSPACE_MEMBER)
def runtime_info(req_context: Request):
    """Return the active platform profile and backend service URL."""
    return runtime_info_action(req_context)


@router.get(
    "/services",
    response_model=list[ComputeServiceInfo],
    dependencies=_WORKSPACE_MEMBER,
)
def list_compute_services():
    """Return service status for compute dependencies."""
    return list_compute_services_action()


@router.get("/services/port-forwards/status", dependencies=_WORKSPACE_MEMBER)
def port_forward_status():
    """Port-forward lifecycle is now managed by the compassx CLI launcher."""
    return port_forward_status_action()


@router.post("/services/port-forwards/recover", dependencies=_WORKSPACE_MEMBER)
async def recover_port_forwards():
    """Port-forward lifecycle is now managed by the compassx CLI launcher."""
    return await recover_port_forwards_action()


@router.post("/services/{service_name}/{action}", response_model=ComputeServiceInfo)
def control_compute_service(
    service_name: str,
    action: str,
    guard: Guard = Depends(get_guard),
):
    """Start, stop, or restart a compute service."""
    return control_compute_service_action(service_name, action, guard)


@router.post("/resources", response_model=ComputeResourceResponse, status_code=201)
def create_compute_resource(
    req_context: Request,
    body: ComputeResourceRequest,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new compute resource configuration."""
    return create_compute_resource_action(req_context, body, db, guard)


@router.put("/resources/{resource_id}", response_model=ComputeResourceResponse)
def update_compute_resource(
    req_context: Request,
    resource_id: str,
    body: ComputeResourceUpdateRequest,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update a compute resource configuration and apply changes."""
    return update_compute_resource_action(req_context, resource_id, body, db, guard)


@router.post("/resources/serverless/ensure", response_model=ComputeResourceStatus)
def ensure_serverless_compute(
    req_context: Request,
    body: EnsureServerlessRequest | None = None,
    notebook_id: str | None = Query(None),
    notebook_name: str | None = Query(None),
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Ensure a serverless compute pod exists for a notebook (or workspace) and return its status."""
    return ensure_serverless_compute_action(req_context, body, notebook_id, notebook_name, db, guard)


@router.get("/resources", response_model=list[ComputeResourceStatus])
def list_compute_resources(
    req_context: Request,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List the compute resources in this workspace the caller may see."""
    return list_compute_resources_action(req_context, db, guard)


@router.get("/resources/{resource_id}", response_model=ComputeResourceStatus)
def get_compute_resource_status(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get a compute resource with current pod status if running."""
    return get_compute_resource_status_action(req_context, resource_id, db, guard)


@router.get("/resources/{resource_id}/metrics", response_model=ComputeMetricsResponse)
def get_compute_resource_metrics(
    req_context: Request,
    resource_id: str,
    range: str = Query(default="15m", pattern="^(15m|1h|6h|24h)$"),
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get live CPU & Memory usage along with Prometheus time-series telemetry."""
    return get_compute_resource_metrics_action(req_context, resource_id, range, db, guard)


@router.delete("/resources/{resource_id}")
def delete_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a compute resource configuration."""
    return delete_compute_resource_action(req_context, resource_id, db, guard)


@router.post("/resources/{resource_id}/start", response_model=dict, status_code=201)
def start_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start a pod from a compute resource configuration."""
    return start_compute_resource_action(req_context, resource_id, db, guard)


@router.post("/resources/{resource_id}/stop")
def stop_compute_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop the running pod for a compute resource."""
    return stop_compute_resource_action(req_context, resource_id, db, guard)


@router.get("/resources/{resource_id}/logs")
async def get_resource_logs(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stream pod logs for the running pod owned by a compute resource."""
    return await get_resource_logs_action(req_context, resource_id, db, guard)


@router.get("/resources/{resource_id}/kernel-info")
def get_kernel_info(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Return notebook kernel connection info for a running compute resource."""
    return get_kernel_info_action(req_context, resource_id, db, guard)


@router.post("/resources/{resource_id}/start-kernel")
def start_kernel_for_resource(
    req_context: Request,
    resource_id: str,
    db=Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start an EG kernel for the running pod owned by a compute resource."""
    return start_kernel_for_resource_action(req_context, resource_id, db, guard)


from app.sandbox.routes import router as sandbox_router  # noqa: E402
router.include_router(sandbox_router)
