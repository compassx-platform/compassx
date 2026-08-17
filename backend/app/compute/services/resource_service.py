"""Service for persistent all-purpose compute resources."""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.compute_resources import ComputeResource
from compute.config import compute_settings
from compute.manager import ComputeManager, JobNotFoundError, get_compute_manager
from compute.profiles import get_profile
from compute.schemas import ComputeResourceRequest, ComputeResourceResponse, ComputeResourceStatus
from compassx.runtime.db_models import PlatformRuntime

logger = logging.getLogger(__name__)


def platform_enabled() -> bool:
    """Feature flag loaded from the same settings source as the backend."""
    return bool(compute_settings.COMPASSX_PLATFORM_ENABLED)


def _run_async(coro):
    """Bridge sync service methods to the async platform layer.

    Router endpoints are sync (FastAPI runs them in a threadpool), so there
    is no running loop in this thread and asyncio.run is safe.
    """
    return asyncio.run(coro)


class ComputeResourceService:
    """Manage persistent compute resources and their linked deployments."""

    def __init__(self, db: Session, runtime_manager=None):
        """runtime_manager: platform RuntimeManager (DI). When provided and
        COMPASSX_PLATFORM_ENABLED is set, lifecycle operations go through the
        deployment-independent platform layer instead of ComputeManager."""
        self.db = db
        self.manager: ComputeManager = get_compute_manager()
        self.runtime_manager = runtime_manager

    def _use_platform(self) -> bool:
        return self.runtime_manager is not None and platform_enabled()

    def _mark_missing_runtime_stopped(self, resource: ComputeResource) -> str:
        """Reconcile persisted intent when its infrastructure no longer exists."""
        resource.desired_status = "stopped"
        resource.pod_name = None
        self.db.commit()
        self.db.refresh(resource)
        logger.warning(
            "Compute runtime %s is missing; reconciled desired status to stopped",
            resource.id,
        )
        return "Runtime was not found and has been marked stopped. Start the compute to recreate it."

    def _normalize_platform_runtime_driver(self, runtime_id: str) -> None:
        """Sync platform-runtime driver to match the active profile's default driver.

        Prevents routing errors when switching profiles or when records were created
        under a different compute driver.
        """
        if not self.runtime_manager:
            return
        target_driver = getattr(
            getattr(self.runtime_manager, "resource_manager", None),
            "default_driver",
            None,
        )
        if not target_driver:
            return

        row = self.db.query(PlatformRuntime).filter(PlatformRuntime.runtime_id == runtime_id).first()
        if row is None or row.driver == target_driver:
            return

        logger.warning(
            "Normalizing platform runtime %s driver from %s to active profile driver %s",
            runtime_id,
            row.driver,
            target_driver,
        )
        row.driver = target_driver
        row.infra_id = None
        row.phase = "missing"
        row.updated_at = datetime.utcnow()
        self.db.commit()

    def _runtime_options(self, resource: ComputeResource) -> dict:
        profile = get_profile(resource.profile, compute_settings.COMPASSX_ENV)
        return {
            "profile_id": profile.id,
            "requests": profile.requests,
            "limits": profile.limits,
            "custom_image": resource.custom_image,
            "extra_env": json.loads(resource.extra_env) if resource.extra_env else {},
        }

    def _deployment_name_for(self, resource_id: str) -> str:
        return f"compassx-compute-{resource_id}"

    def _to_response(self, resource: ComputeResource) -> ComputeResourceResponse:
        return ComputeResourceResponse(
            id=resource.id,
            name=resource.name,
            runtime=resource.runtime,
            profile=resource.profile,
            user_id=resource.user_id,
            created_by=resource.created_by,
            created_at=resource.created_at,
            description=resource.description,
            deployment_name=resource.deployment_name,
            desired_status=resource.desired_status,
            is_default=bool(resource.is_default),
        )

    def create_resource(
        self,
        request: ComputeResourceRequest,
        user_id: str,
        created_by: str,
        *,
        workspace_id: str | None = None,
        is_default: bool = False,
        auto_start: bool = False,
    ) -> ComputeResourceResponse:
        """Create a new compute resource configuration."""
        get_profile(request.profile.value, compute_settings.COMPASSX_ENV)

        resource_id = uuid.uuid4().hex[:8]
        now = datetime.utcnow()

        resource = ComputeResource(
            id=resource_id,
            workspace_id=workspace_id,
            name=request.name,
            runtime=request.runtime.value,
            profile=request.profile.value,
            user_id=user_id,
            created_by=created_by,
            custom_image=request.custom_image,
            extra_env=json.dumps(request.extra_env or {}),
            created_at=now,
            description=request.description,
            deployment_name=self._deployment_name_for(resource_id),
            desired_status="running" if auto_start else "stopped",
            is_default=is_default,
        )

        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        logger.info("Created compute resource: %s for user %s", resource_id, user_id)

        if auto_start:
            self.start_resource(resource_id, user_id, workspace_id)
            self.db.refresh(resource)

        return self._to_response(resource)

    def list_resources(self, user_id: str, workspace_id: str | None = None) -> list[ComputeResourceResponse]:
        query = self.db.query(ComputeResource).filter(
            ComputeResource.user_id == user_id
        )
        if workspace_id:
            query = query.filter(ComputeResource.workspace_id == workspace_id)
        else:
            query = query.filter(ComputeResource.workspace_id == None)
        resources = query.order_by(ComputeResource.is_default.desc(), ComputeResource.created_at.asc()).all()
        return [self._to_response(resource) for resource in resources]
    def list_resources_with_status(
        self, user_id: str, workspace_id: str | None = None
    ) -> list[ComputeResourceStatus]:
        """List all resources with their current runtime status."""
        query = self.db.query(ComputeResource).filter(
            ComputeResource.user_id == user_id
        )
        if workspace_id:
            query = query.filter(ComputeResource.workspace_id == workspace_id)
        else:
            query = query.filter(ComputeResource.workspace_id == None)
        resources = query.order_by(
            ComputeResource.is_default.desc(), ComputeResource.created_at.asc()
        ).all()
        results = []
        for resource in resources:
            try:
                results.append(
                    self.get_resource_with_status(resource.id, user_id, workspace_id)
                )
            except Exception as exc:  # noqa: BLE001 - keep one failed runtime from failing the list
                logger.warning(
                    "Unable to get status for compute resource %s: %s",
                    resource.id,
                    exc,
                )
                results.append(
                    ComputeResourceStatus(
                        id=resource.id,
                        name=resource.name,
                        runtime=resource.runtime,
                        profile=resource.profile,
                        user_id=resource.user_id,
                        created_by=resource.created_by,
                        created_at=resource.created_at,
                        description=resource.description,
                        job_id=resource.id,
                        deployment_name=resource.deployment_name,
                        desired_status=resource.desired_status,
                        is_default=bool(resource.is_default),
                        runtime_id=resource.id,
                        phase="Unknown",
                        message="Runtime status unavailable; check the compute backend connection.",
                    )
                )
        return results

    def _get_resource_row(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> ComputeResource:
        query = self.db.query(ComputeResource).filter(
            ComputeResource.id == resource_id,
            ComputeResource.user_id == user_id,
        )
        if workspace_id:
            query = query.filter(ComputeResource.workspace_id == workspace_id)
        else:
            query = query.filter(ComputeResource.workspace_id == None)
        resource = query.first()
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        if not resource.deployment_name:
            resource.deployment_name = self._deployment_name_for(resource.id)
            self.db.commit()
            self.db.refresh(resource)
        return resource

    def get_resource(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> ComputeResourceResponse:
        return self._to_response(self._get_resource_row(resource_id, user_id, workspace_id))

    def get_resource_with_status(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> ComputeResourceStatus:
        resource = self._get_resource_row(resource_id, user_id, workspace_id)

        if self._use_platform():
            return self._platform_status(resource)

        job_id = resource.id
        pod_name = None
        phase = "Stopped" if resource.desired_status == "stopped" else None
        started_at = None
        finished_at = None
        message = None

        exists, replicas = self.manager.get_deployment_status(resource.deployment_name)
        if not exists:
            if resource.desired_status == "running":
                message = self._mark_missing_runtime_stopped(resource)
            else:
                resource.pod_name = None
            phase = "Stopped"
        elif replicas == 0:
            resource.pod_name = None
            phase = "Stopped"
        else:
            try:
                status = self.manager.get_job_status(
                    job_id,
                    runtime=resource.runtime,
                    profile=resource.profile,
                    user_id=resource.user_id,
                    created_at=resource.created_at,
                )
                pod_name = status.pod_name
                phase = status.phase
                started_at = status.started_at
                finished_at = status.finished_at
                message = status.message
                resource.pod_name = pod_name
            except JobNotFoundError:
                resource.pod_name = None
                phase = "Pending"

        self.db.commit()
        self.db.refresh(resource)

        return ComputeResourceStatus(
            id=resource.id,
            name=resource.name,
            runtime=resource.runtime,
            profile=resource.profile,
            user_id=resource.user_id,
            created_by=resource.created_by,
            created_at=resource.created_at,
            description=resource.description,
            job_id=job_id,
            deployment_name=resource.deployment_name,
            desired_status=resource.desired_status,
            is_default=bool(resource.is_default),
            runtime_id=resource.id,
            pod_name=pod_name or resource.pod_name,
            phase=phase,
            started_at=started_at,
            finished_at=finished_at,
            message=message,
        )

    def _platform_status(self, resource: ComputeResource) -> ComputeResourceStatus:
        """Status via the platform layer (deployment-independent)."""
        from compassx.models import DriverUnavailableError, RuntimeNotFoundError, RuntimePhase

        phase_map = {
            RuntimePhase.CREATING: "Pending",
            RuntimePhase.PENDING: "Pending",
            RuntimePhase.RUNNING: "Running",
            RuntimePhase.STOPPING: "Stopping",
            RuntimePhase.STOPPED: "Stopped",
            RuntimePhase.FAILED: "Failed",
            RuntimePhase.SUSPENDED: "Stopped",
            RuntimePhase.DELETED: "Stopped",
            RuntimePhase.MISSING: "Stopped",
            RuntimePhase.UNKNOWN: "Unknown",
        }
        phase = "Stopped"
        started_at = None
        finished_at = None
        message = None
        try:
            self._normalize_platform_runtime_driver(resource.id)
            info = _run_async(self.runtime_manager.get_status(resource.id))
            phase = phase_map.get(info.phase, "Unknown")
            started_at = info.started_at
            finished_at = info.finished_at
            message = info.message or None
            if (
                info.phase == RuntimePhase.MISSING
                and (resource.desired_status != "stopped" or resource.pod_name)
            ):
                message = self._mark_missing_runtime_stopped(resource)
        except DriverUnavailableError as exc:
            if resource.desired_status == "stopped":
                phase = "Stopped"
            else:
                phase = "Unknown"
                message = f"Compute driver unavailable: {exc}"
        except RuntimeNotFoundError:
            phase = "Stopped"
            if resource.desired_status != "stopped" or resource.pod_name:
                message = self._mark_missing_runtime_stopped(resource)

        # pod_name kept for API compatibility; platform layer never exposes it.
        return ComputeResourceStatus(
            id=resource.id,
            name=resource.name,
            runtime=resource.runtime,
            profile=resource.profile,
            user_id=resource.user_id,
            created_by=resource.created_by,
            created_at=resource.created_at,
            description=resource.description,
            job_id=resource.id,
            deployment_name=resource.deployment_name,
            desired_status=resource.desired_status,
            is_default=bool(resource.is_default),
            runtime_id=resource.id,
            pod_name=None,
            phase=phase,
            started_at=started_at,
            finished_at=finished_at,
            message=message,
        )

    def delete_resource(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> None:
        resource = self._get_resource_row(resource_id, user_id, workspace_id)
        if self._use_platform():
            from compassx.models import DriverUnavailableError, RuntimeNotFoundError

            try:
                self._normalize_platform_runtime_driver(resource.id)
                _run_async(self.runtime_manager.delete_runtime(resource.id))
            except DriverUnavailableError:
                self._normalize_platform_runtime_driver(resource.id)
                try:
                    _run_async(self.runtime_manager.delete_runtime(resource.id))
                except RuntimeNotFoundError:
                    pass
            except RuntimeNotFoundError:
                pass
            except Exception:
                logger.warning("Failed deleting platform runtime before delete: %s", resource.id)
        elif resource.deployment_name:
            try:
                self.manager.delete_resource_job(resource.deployment_name)
            except Exception:
                logger.warning("Failed stopping deployment before delete: %s", resource.deployment_name)

        self.db.delete(resource)
        self.db.commit()
        logger.info("Deleted compute resource: %s", resource_id)

    def start_resource(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> dict:
        resource = self._get_resource_row(resource_id, user_id, workspace_id)

        if self._use_platform():
            from compassx.models import DriverUnavailableError, RuntimeNotFoundError

            rm = self.runtime_manager

            async def _start():
                try:
                    self._normalize_platform_runtime_driver(resource.id)
                    await rm.start_runtime(resource.id)
                except (DriverUnavailableError, RuntimeNotFoundError):
                    self._normalize_platform_runtime_driver(resource.id)
                    try:
                        await rm.start_runtime(resource.id)
                    except RuntimeNotFoundError:
                        await rm.create_runtime(
                            resource.runtime,
                            runtime_id=resource.id,
                            user_id=user_id,
                            workspace_id=workspace_id or "",
                            options=self._runtime_options(resource),
                        )

            _run_async(_start())
            resource.desired_status = "running"
            resource.pod_name = None
            self.db.commit()
            self.db.refresh(resource)
            logger.info("Started platform runtime for resource: %s", resource_id)
            return {
                "job_id": resource.id,
                "runtime_id": resource.id,
                "deployment_name": resource.deployment_name,
                "pod_name": None,
                "status": "Pending",
            }

        profile = get_profile(resource.profile, compute_settings.COMPASSX_ENV)
        extra_env = json.loads(resource.extra_env) if resource.extra_env else None

        job = self.manager.create_resource_job(
            resource_id=resource.id,
            resource_name=resource.name,
            runtime=resource.runtime,
            profile=profile,
            user_id=user_id,
            custom_image=resource.custom_image,
            extra_env=extra_env,
            deployment_name=resource.deployment_name,
        )

        resource.desired_status = "running"
        resource.pod_name = None
        self.db.commit()
        self.db.refresh(resource)

        logger.info("Started deployment for resource: %s", resource_id)
        return {
            "job_id": job.job_id,
            "runtime_id": resource.id,
            "deployment_name": resource.deployment_name,
            "pod_name": job.pod_name,
            "status": job.status,
        }

    def stop_resource_pod(self, resource_id: str, user_id: str, workspace_id: str | None = None) -> None:
        resource = self._get_resource_row(resource_id, user_id, workspace_id)

        if self._use_platform():
            from compassx.models import DriverUnavailableError, RuntimeNotFoundError

            try:
                self._normalize_platform_runtime_driver(resource.id)
                _run_async(self.runtime_manager.stop_runtime(resource.id))
            except DriverUnavailableError:
                self._normalize_platform_runtime_driver(resource.id)
                try:
                    _run_async(self.runtime_manager.stop_runtime(resource.id))
                except RuntimeNotFoundError:
                    pass
            except RuntimeNotFoundError:
                raise ValueError(f"No runtime found for resource: {resource_id}")
            resource.desired_status = "stopped"
            resource.pod_name = None
            self.db.commit()
            logger.info("Stopped platform runtime for resource: %s", resource_id)
            return

        if not resource.deployment_name:
            raise ValueError(f"No deployment configured for resource: {resource_id}")

        stopped = self.manager.stop_resource_job(resource.deployment_name)
        if not stopped:
            raise ValueError(f"No deployment found for resource: {resource_id}")

        resource.desired_status = "stopped"
        resource.pod_name = None
        self.db.commit()
        logger.info("Stopped deployment for resource: %s", resource_id)

    def reconcile_runtime_states(self) -> int:
        """Reconcile running database records with actual infrastructure state."""
        resources = self.db.query(ComputeResource).filter(
            ComputeResource.desired_status == "running"
        ).all()
        reconciled = 0
        for resource in resources:
            try:
                if self._use_platform():
                    status = self._platform_status(resource)
                else:
                    status = self.get_resource_with_status(
                        resource.id,
                        resource.user_id,
                        resource.workspace_id,
                    )
                if status.desired_status == "stopped":
                    reconciled += 1
            except Exception:
                self.db.rollback()
                logger.exception("Failed to reconcile compute runtime %s", resource.id)
        logger.info(
            "Compute startup reconciliation checked %d running resource(s); marked %d stopped",
            len(resources),
            reconciled,
        )
        return reconciled

    def ensure_default_resource(self) -> ComputeResource | None:
        """Create the default compute resource, preserving an existing user's intent."""
        if not compute_settings.DEFAULT_COMPUTE_ENABLED:
            return None

        resource = self.db.query(ComputeResource).filter(
            ComputeResource.user_id == compute_settings.DEFAULT_COMPUTE_USER_ID,
            ComputeResource.is_default.is_(True),
        ).first()

        if not resource:
            request = ComputeResourceRequest(
                name=compute_settings.DEFAULT_COMPUTE_NAME,
                runtime=compute_settings.DEFAULT_COMPUTE_RUNTIME,
                profile=compute_settings.resolved_default_compute_profile(),
                description="Auto-created default compute for fast notebook access.",
            )
            self.create_resource(
                request,
                compute_settings.DEFAULT_COMPUTE_USER_ID,
                compute_settings.DEFAULT_COMPUTE_CREATED_BY,
                is_default=True,
                auto_start=True,
            )
            resource = self.db.query(ComputeResource).filter(
                ComputeResource.user_id == compute_settings.DEFAULT_COMPUTE_USER_ID,
                ComputeResource.is_default.is_(True),
            ).first()
            logger.info("Default compute resource created")
        else:
            if resource.desired_status == "running":
                self.get_resource_with_status(
                    resource.id,
                    resource.user_id,
                    resource.workspace_id,
                )
            logger.info("Default compute resource reconciled")

        return resource
