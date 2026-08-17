"""Publish service — §6 publish flow.

Steps:
  1. Provision a dedicated production pod (never reuses a branch pod)
  2. Materialize the chosen commit onto the production pod's disk
  3. Run dependency install (cache-backed, same as branch pod startup)
  4. On health check pass, atomically update app_production_pointer + flip routing
  5. Keep prior production pod warm for grace window (default 10 min)
  6. Tear down prior pod after grace window if not switched back
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import App, AppPod, AppProductionPointer
from app.apps.services.credential_service import CredentialService
from app.apps.services.pod_service import PodService
from app.apps.services.source_control.factory import get_source_control_backend

logger = logging.getLogger(__name__)

# Grace window before tearing down the prior production pod after a publish
_GRACE_WINDOW_SECONDS = 600  # 10 minutes


class PublishService:
    """Orchestrates the full §6 publish flow."""

    def __init__(self, db: Session):
        self._db = db
        self._pod_svc = PodService(db)
        self._cred_svc = CredentialService(db)

    async def publish(
        self,
        app_id: uuid.UUID,
        commit_id: uuid.UUID,
        source_branch_id: uuid.UUID,
        switched_by: uuid.UUID,
    ) -> AppPod:
        """Run the full publish flow. Returns the new production pod."""
        app: Optional[App] = self._db.query(App).filter(App.app_id == app_id).one_or_none()
        if app is None:
            raise ValueError(f"App {app_id} not found")

        # Record the prior production pod for grace-window teardown
        prior_pod: Optional[AppPod] = self._get_current_production_pod(app_id)

        # Step 1 — Mint scoped token for new production pod
        scoped_token = await self._cred_svc.mint_scoped_token(app_id)

        # Step 2 — Provision new production pod
        new_pod = await self._pod_svc.provision_production_pod(
            app_id=app_id,
            commit_id=commit_id,
            scoped_token=scoped_token,
        )

        # Step 3 — Materialize commit onto pod disk
        sc = get_source_control_backend(db=self._db, workspace_id=app.workspace_id)
        target_path = f"/workspace-production/{app_id}/{new_pod.pod_id}"
        await sc.materialize(commit_id=commit_id, target_path=target_path)

        # Step 4 — Wait for health check
        ready = await self._pod_svc.wait_for_ready(new_pod, timeout_seconds=180)
        if not ready:
            new_pod.status = "failed"
            self._db.flush()
            raise RuntimeError(f"Production pod {new_pod.k8s_pod_name} failed health check — publish aborted")

        # Step 5 — Atomically update production pointer
        pointer = (
            self._db.query(AppProductionPointer)
            .filter(AppProductionPointer.app_id == app_id)
            .one_or_none()
        )
        if pointer is None:
            pointer = AppProductionPointer(
                app_id=app_id,
                current_commit_id=commit_id,
                source_branch_id=source_branch_id,
                switched_by=switched_by,
            )
            self._db.add(pointer)
        else:
            pointer.current_commit_id = commit_id
            pointer.source_branch_id = source_branch_id
            pointer.switched_at = datetime.now(timezone.utc)
            pointer.switched_by = switched_by

        self._db.flush()
        logger.info("Production pointer updated: app=%s commit=%s", app_id, commit_id)

        # Step 6 — Schedule prior pod teardown after grace window (background)
        if prior_pod is not None:
            asyncio.create_task(
                self._teardown_after_grace(prior_pod.pod_id, _GRACE_WINDOW_SECONDS)
            )

        return new_pod

    async def get_production_status(self, app_id: uuid.UUID) -> dict:
        """Return current production pointer and pod status."""
        pointer: Optional[AppProductionPointer] = (
            self._db.query(AppProductionPointer)
            .filter(AppProductionPointer.app_id == app_id)
            .one_or_none()
        )
        if pointer is None:
            return {
                "app_id": str(app_id),
                "current_commit_id": None,
                "source_branch_id": None,
                "switched_at": None,
                "switched_by": None,
                "pod_status": None,
                "preview_url": None,
            }

        prod_pod = self._get_current_production_pod(app_id)
        return {
            "app_id": str(app_id),
            "current_commit_id": str(pointer.current_commit_id) if pointer.current_commit_id else None,
            "source_branch_id": str(pointer.source_branch_id) if pointer.source_branch_id else None,
            "switched_at": pointer.switched_at.isoformat() if pointer.switched_at else None,
            "switched_by": str(pointer.switched_by) if pointer.switched_by else None,
            "pod_status": prod_pod.status if prod_pod else None,
            "preview_url": prod_pod.preview_url if prod_pod else None,
        }

    def _get_current_production_pod(self, app_id: uuid.UUID) -> Optional[AppPod]:
        return (
            self._db.query(AppPod)
            .filter(
                AppPod.app_id == app_id,
                AppPod.pod_kind == "production",
                AppPod.status.in_(["starting", "running"]),
            )
            .order_by(AppPod.created_at.desc())
            .first()
        )

    async def _teardown_after_grace(self, pod_id: uuid.UUID, delay_seconds: int) -> None:
        """Wait for grace window then terminate the prior production pod."""
        await asyncio.sleep(delay_seconds)
        try:
            await self._pod_svc.terminate_pod(pod_id)
            logger.info("Prior production pod %s torn down after grace window", pod_id)
        except Exception as exc:
            logger.warning("Grace-window teardown failed for pod %s: %s", pod_id, exc)
