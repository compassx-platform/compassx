"""Unified Reaper Service — Centralized automated idle suspension and stale workspace garbage collection.

Manages inactivity detection, user-configured auto-shutdown, and storage reclamation across:
1. Dev Sandbox Pods (compassx-app-dev-<app_id>) — Omnigent AI & Dev Studio.
2. Deployed Production App Pods (compassx-app-<app_id>) — Streamlit, FastAPI, React apps.
3. Compute Runtime & Interactive Kernel Pods (compassx-runtime-<id>) — Spark, Ray, DuckDB, Flink.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from app.config import settings
from app.services.drivers.factory import driver_factory

logger = logging.getLogger(__name__)

# Default timeouts
DEFAULT_DEV_IDLE_SUSPEND_SECONDS = 3600    # 1 hour default for dev sandboxes
DEFAULT_APP_IDLE_SUSPEND_SECONDS = 7200    # 2 hours default for deployed apps (when auto_suspend_enabled=True)
DEFAULT_COMPUTE_IDLE_SUSPEND_SECONDS = 300 # 5 minutes default for compute runtimes / notebooks
DEFAULT_STALE_REAP_DAYS = 30               # 30 days offline -> reclaim storage
SWEEP_INTERVAL_SECONDS = 30                # Sweep check every 30 seconds


def _parse_datetime(dt_val: Any) -> Optional[datetime]:
    """Safely parse datetime object or ISO-formatted string into timezone-aware UTC datetime."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    if isinstance(dt_val, str) and dt_val.strip():
        try:
            cleaned = dt_val.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None
    return None


class SandboxReaperService:
    """Manages automatic idle suspension and stale resource garbage collection across all pod types."""

    def __init__(
        self,
        idle_timeout_seconds: int = DEFAULT_DEV_IDLE_SUSPEND_SECONDS,
        stale_reap_days: int = DEFAULT_STALE_REAP_DAYS,
        sweep_interval_seconds: int = SWEEP_INTERVAL_SECONDS,
    ):
        self.idle_timeout_seconds = getattr(settings, "DEV_SANDBOX_IDLE_TIMEOUT_SECONDS", idle_timeout_seconds)
        self.app_idle_timeout_seconds = getattr(settings, "APP_RUNTIME_IDLE_TIMEOUT_SECONDS", DEFAULT_APP_IDLE_SUSPEND_SECONDS)
        self.compute_idle_timeout_seconds = getattr(settings, "COMPUTE_RUNTIME_IDLE_TIMEOUT_SECONDS", DEFAULT_COMPUTE_IDLE_SUSPEND_SECONDS)
        self.stale_reap_days = getattr(settings, "DEV_SANDBOX_STALE_REAP_DAYS", stale_reap_days)
        self.sweep_interval_seconds = sweep_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background reaper loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="compassx-unified-reaper")
        logger.info(
            "Unified Reaper Service started (dev_idle=%ss, app_idle=%ss, compute_idle=%ss, sweep_interval=%ss)",
            self.idle_timeout_seconds,
            self.app_idle_timeout_seconds,
            self.compute_idle_timeout_seconds,
            self.sweep_interval_seconds,
        )

    async def shutdown(self) -> None:
        """Gracefully stop the background reaper loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Unified Reaper Service stopped.")

    async def _run_loop(self) -> None:
        """Continuous sweep loop."""
        # Initial sleep before first sweep to let server bootstrap
        await asyncio.sleep(15)
        while self._running:
            try:
                await self.sweep_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Unified reaper sweep encountered an error: %s", e)
            await asyncio.sleep(self.sweep_interval_seconds)

    async def sweep_once(self) -> None:
        """Execute one complete idle and stale sweep across dev sandboxes, apps, and compute runtimes."""
        await asyncio.to_thread(self._sync_sweep_idle_workspaces)
        await asyncio.to_thread(self._sync_sweep_stale_workspaces)
        await asyncio.to_thread(self._sync_sweep_idle_apps)
        await asyncio.to_thread(self._sync_sweep_idle_compute_resources)

    # ── 1. Dev Sandboxes (Omnigent AI & Dev Studio) ───────────────────────────

    def _sync_sweep_idle_workspaces(self) -> None:
        """Identify active dev sandboxes with no activity beyond idle threshold and suspend compute."""
        try:
            from app.database import SystemSessionLocal
            from app.models.dev_workspace import DevWorkspace
            from app.models.app import App
            from app.services.omnigent_dev_service import omnigent_dev_service

            now = datetime.now(timezone.utc)

            with SystemSessionLocal() as db:
                active_workspaces = (
                    db.query(DevWorkspace)
                    .filter(DevWorkspace.status == "active")
                    .all()
                )

                if not active_workspaces:
                    return

                for ws in active_workspaces:
                    app = db.query(App).filter(App.id == ws.app_id).first()
                    if not app:
                        continue

                    # Read app-specific configuration
                    cfg = app.config or {}
                    app_cfg = cfg.get("dev_sandbox") or cfg.get("lifecycle", {}).get("dev_sandbox", {})
                    auto_suspend_enabled = app_cfg.get("auto_suspend_enabled", True)

                    # If auto-suspend is disabled for this dev sandbox, preserve compute
                    if not auto_suspend_enabled:
                        continue

                    # Resolve per-app idle timeout
                    idle_timeout_mins = app_cfg.get("idle_timeout_minutes")
                    if idle_timeout_mins is not None:
                        try:
                            idle_timeout_secs = max(300, int(idle_timeout_mins) * 60)
                        except (ValueError, TypeError):
                            idle_timeout_secs = self.idle_timeout_seconds
                    else:
                        idle_timeout_secs = self.idle_timeout_seconds

                    cutoff = now - timedelta(seconds=idle_timeout_secs)
                    last_active = _parse_datetime(ws.last_active_at)

                    if not last_active or last_active < cutoff:
                        # Check runtime status
                        dev_driver = driver_factory.get_dev_driver()
                        status = dev_driver.get_dev_status(app)
                        if status.get("status") == "active":
                            # Multi-layer active work verification:
                            # 1. Omnigent host runner online / active task sessions
                            # 2. Workspace filesystem mtime changes
                            has_active_work = omnigent_dev_service.check_app_has_active_work(app, ws, cutoff)
                            if has_active_work:
                                logger.info(
                                    "Dev sandbox for app '%s' (%s) has active Omnigent/filesystem work; keeping alive.",
                                    app.name,
                                    app.id,
                                )
                                continue

                            logger.info(
                                "Suspending idle dev sandbox for app '%s' (%s) — last active at %s (timeout=%ss)",
                                app.name,
                                app.id,
                                last_active.isoformat() if last_active else "unknown",
                                idle_timeout_secs,
                            )
                            omnigent_dev_service.suspend_dev_session(app)
        except Exception as err:
            logger.debug("Error during idle sandbox sweep: %s", err)

    def _sync_sweep_stale_workspaces(self) -> None:
        """Identify abandoned dev workspaces older than stale threshold and clean up disk allocations."""
        try:
            from app.database import SystemSessionLocal
            from app.models.dev_workspace import DevWorkspace
            from app.models.app import App

            now = datetime.now(timezone.utc)

            with SystemSessionLocal() as db:
                stale_candidates = (
                    db.query(DevWorkspace)
                    .filter(DevWorkspace.status.in_(["stopped", "suspended", "inactive"]))
                    .all()
                )

                if not stale_candidates:
                    return

                for ws in stale_candidates:
                    app = db.query(App).filter(App.id == ws.app_id).first()
                    if not app:
                        continue

                    cfg = app.config or {}
                    app_cfg = cfg.get("dev_sandbox") or cfg.get("lifecycle", {}).get("dev_sandbox", {})
                    auto_reap_enabled = app_cfg.get("auto_reap_enabled", True)

                    # If auto-reap is disabled for this app, preserve storage indefinitely
                    if not auto_reap_enabled:
                        continue

                    stale_days = app_cfg.get("stale_reap_days")
                    if stale_days is not None:
                        try:
                            stale_reap_days = max(1, int(stale_days))
                        except (ValueError, TypeError):
                            stale_reap_days = self.stale_reap_days
                    else:
                        stale_reap_days = self.stale_reap_days

                    stale_cutoff = now - timedelta(days=stale_reap_days)
                    last_active = _parse_datetime(ws.last_active_at)

                    if last_active and last_active < stale_cutoff:
                        logger.info(
                            "Reaping stale dev workspace '%s' (app %s) inactive for > %s days",
                            ws.folder_path,
                            ws.app_id,
                            stale_reap_days,
                        )

                        # Delete folder from shared PVC via driver
                        dev_driver = driver_factory.get_dev_driver()
                        if hasattr(dev_driver, "delete_workspace_folder"):
                            try:
                                dev_driver.delete_workspace_folder(ws.folder_path)
                            except Exception:
                                pass

                        ws.status = "archived"
                        db.commit()
        except Exception as err:
            logger.debug("Error during stale workspace reap sweep: %s", err)

    # ── 2. Deployed Production Apps (Streamlit / FastAPI / React) ─────────────

    def _sync_sweep_idle_apps(self) -> None:
        """Identify deployed production apps with auto_suspend_enabled and no recent traffic beyond idle threshold."""
        try:
            from app.database import SystemSessionLocal
            from app.models.app import App
            from app.services.app_runner import app_runner_service

            now = datetime.now(timezone.utc)

            with SystemSessionLocal() as db:
                active_apps = (
                    db.query(App)
                    .filter(App.status.in_(["active", "running"]))
                    .all()
                )

                if not active_apps:
                    return

                for app in active_apps:
                    cfg = app.config or {}
                    app_cfg = cfg.get("app_runtime") or cfg.get("lifecycle", {}).get("app_runtime", {})
                    # By default, deployed apps run 24/7 (auto_suspend_enabled=False) unless explicitly toggled ON by user
                    auto_suspend_enabled = app_cfg.get("auto_suspend_enabled", False)
                    if not auto_suspend_enabled:
                        continue

                    idle_timeout_mins = app_cfg.get("idle_timeout_minutes")
                    if idle_timeout_mins is not None:
                        try:
                            idle_timeout_secs = max(300, int(idle_timeout_mins) * 60)
                        except (ValueError, TypeError):
                            idle_timeout_secs = self.app_idle_timeout_seconds
                    else:
                        idle_timeout_secs = self.app_idle_timeout_seconds

                    cutoff = now - timedelta(seconds=idle_timeout_secs)

                    # Determine last activity timestamp
                    last_accessed_raw = (
                        app_cfg.get("last_accessed_at")
                        or cfg.get("last_accessed_at")
                        or cfg.get("lifecycle", {}).get("last_accessed_at")
                        or app.updated_at
                        or app.created_at
                    )
                    last_accessed = _parse_datetime(last_accessed_raw)

                    if not last_accessed or last_accessed < cutoff:
                        # Check real runtime status via driver
                        status_info = app_runner_service.get_runtime_status(app)
                        if status_info.get("status") in ("active", "running"):
                            logger.info(
                                "Suspending idle deployed app '%s' (%s) — last accessed at %s (timeout=%ss)",
                                app.name,
                                app.id,
                                last_accessed.isoformat() if last_accessed else "unknown",
                                idle_timeout_secs,
                            )
                            try:
                                app_runner_service.stop_app(app)
                                app.status = "stopped"
                                db.commit()
                            except Exception as stop_err:
                                logger.warning("Could not stop idle app %s: %s", app.id, stop_err)
        except Exception as err:
            logger.debug("Error during idle deployed apps sweep: %s", err)

    # ── 3. Compute Runtimes & Kernels (Spark / Ray / DuckDB / Flink) ──────────

    def _sync_sweep_idle_compute_resources(self) -> None:
        """Identify running compute runtimes with auto_suspend_enabled and no activity beyond idle threshold."""
        try:
            from app.database import SystemSessionLocal, AccountSessionLocal
            from app.models.compute_resources import ComputeResource
            from app.compute.services.resource_service import ComputeResourceService
            from app.workspace.models import Account

            now = datetime.now(timezone.utc)

            # 1. Load organization/account level compute settings
            account_compute_cfg = {}
            try:
                with AccountSessionLocal() as acc_db:
                    acc = acc_db.query(Account).first()
                    if acc and acc.settings:
                        account_compute_cfg = acc.settings.get("compute", {})
            except Exception as acc_err:
                logger.debug("Could not query account-level compute settings: %s", acc_err)
                account_compute_cfg = {}

            account_auto_stop_enabled = account_compute_cfg.get("auto_stop_enabled", True)
            account_auto_stop_minutes = account_compute_cfg.get("auto_stop_minutes", 5)
            try:
                account_idle_secs = max(60, int(account_auto_stop_minutes) * 60)
            except (ValueError, TypeError):
                account_idle_secs = self.compute_idle_timeout_seconds

            with SystemSessionLocal() as db:
                running_resources = (
                    db.query(ComputeResource)
                    .filter(ComputeResource.desired_status == "running")
                    .all()
                )

                if not running_resources:
                    return

                resource_service = ComputeResourceService(db)

                for res in running_resources:
                    extra_env = {}
                    if res.extra_env:
                        try:
                            extra_env = json.loads(res.extra_env)
                        except Exception:
                            extra_env = {}

                    lifecycle_cfg = extra_env.get("lifecycle", {})
                    # Per-resource override takes priority; otherwise fall back to account setting
                    res_auto_suspend = lifecycle_cfg.get(
                        "auto_suspend_enabled",
                        extra_env.get("auto_suspend_enabled", account_auto_stop_enabled)
                    )
                    if not res_auto_suspend:
                        continue

                    idle_timeout_mins = lifecycle_cfg.get("idle_timeout_minutes", extra_env.get("idle_timeout_minutes"))
                    if idle_timeout_mins is not None:
                        try:
                            idle_timeout_secs = max(60, int(idle_timeout_mins) * 60)
                        except (ValueError, TypeError):
                            idle_timeout_secs = account_idle_secs
                    else:
                        idle_timeout_secs = account_idle_secs

                    cutoff = now - timedelta(seconds=idle_timeout_secs)

                    # Determine last activity timestamp
                    last_active_raw = (
                        lifecycle_cfg.get("last_active_at")
                        or extra_env.get("last_active_at")
                        or res.created_at
                    )
                    last_active = _parse_datetime(last_active_raw)

                    # Check platform runtime record updated_at if available
                    from compassx.runtime.db_models import PlatformRuntime
                    pr = db.query(PlatformRuntime).filter(PlatformRuntime.runtime_id == res.id).first()
                    if pr and pr.updated_at:
                        pr_updated = _parse_datetime(pr.updated_at)
                        if pr_updated and (not last_active or pr_updated > last_active):
                            last_active = pr_updated

                    if not last_active or last_active < cutoff:
                        logger.info(
                            "Suspending idle compute resource '%s' (%s, runtime=%s) — last active at %s (timeout=%ss)",
                            res.name,
                            res.id,
                            res.runtime,
                            last_active.isoformat() if last_active else "unknown",
                            idle_timeout_secs,
                        )
                        try:
                            resource_service.stop_resource(res.id, user_id=res.user_id, workspace_id=res.workspace_id)
                        except Exception as stop_err:
                            logger.warning("Could not stop idle compute resource %s: %s", res.id, stop_err)
        except Exception as err:
            logger.debug("Error during idle compute resources sweep: %s", err)

    # ── Activity Touch Helpers ───────────────────────────────────────────────

    def touch_app_activity(self, app_id: str) -> None:
        """Record traffic / interaction activity for a deployed production app."""
        try:
            from app.database import SystemSessionLocal
            from app.models.app import App
            from sqlalchemy.orm.attributes import flag_modified

            now_iso = datetime.now(timezone.utc).isoformat()
            with SystemSessionLocal() as db:
                app = db.query(App).filter(App.id == app_id).first()
                if app:
                    cfg = dict(app.config or {})
                    if "lifecycle" not in cfg or not isinstance(cfg["lifecycle"], dict):
                        cfg["lifecycle"] = {}
                    if "app_runtime" not in cfg["lifecycle"] or not isinstance(cfg["lifecycle"]["app_runtime"], dict):
                        cfg["lifecycle"]["app_runtime"] = {}

                    cfg["lifecycle"]["last_accessed_at"] = now_iso
                    cfg["lifecycle"]["app_runtime"]["last_accessed_at"] = now_iso
                    cfg["last_accessed_at"] = now_iso

                    app.config = cfg
                    flag_modified(app, "config")
                    db.commit()
        except Exception as e:
            logger.debug("Failed to touch app activity for %s: %s", app_id, e)

    def touch_dev_sandbox_activity(self, app_id: str, workspace_id: Optional[str] = None) -> None:
        """Record dev interaction activity for an app dev sandbox."""
        try:
            from app.services.omnigent_dev_service import omnigent_dev_service
            omnigent_dev_service.touch_workspace_activity(app_id, workspace_id)
        except Exception as e:
            logger.debug("Failed to touch dev sandbox activity for %s: %s", app_id, e)

    def touch_compute_activity(self, resource_id: str) -> None:
        """Record execution / interaction activity for a compute runtime."""
        try:
            from app.database import SystemSessionLocal
            from app.models.compute_resources import ComputeResource
            from compassx.runtime.db_models import PlatformRuntime

            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            with SystemSessionLocal() as db:
                res = db.query(ComputeResource).filter(ComputeResource.id == resource_id).first()
                if res:
                    env_dict = {}
                    if res.extra_env:
                        try:
                            env_dict = json.loads(res.extra_env)
                        except Exception:
                            env_dict = {}
                    if "lifecycle" not in env_dict or not isinstance(env_dict["lifecycle"], dict):
                        env_dict["lifecycle"] = {}

                    env_dict["lifecycle"]["last_active_at"] = now_iso
                    env_dict["last_active_at"] = now_iso
                    res.extra_env = json.dumps(env_dict)

                pr = db.query(PlatformRuntime).filter(PlatformRuntime.runtime_id == resource_id).first()
                if pr:
                    pr.updated_at = now

                db.commit()
        except Exception as e:
            logger.debug("Failed to touch compute activity for %s: %s", resource_id, e)


# Global singleton instance
sandbox_reaper_service = SandboxReaperService()
unified_reaper_service = sandbox_reaper_service
