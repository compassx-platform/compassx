"""Managed Sandbox Reaper Service — Automated idle suspension and stale workspace garbage collection."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.config import settings
from app.services.drivers.factory import driver_factory

logger = logging.getLogger(__name__)

# Default timeouts
DEFAULT_IDLE_SUSPEND_SECONDS = 7200  # 2 hours of inactivity -> scale-to-zero
DEFAULT_STALE_REAP_DAYS = 30         # 30 days offline -> reclaim storage
SWEEP_INTERVAL_SECONDS = 120        # Sweep check every 2 minutes


class SandboxReaperService:
    """Manages automatic idle suspension and stale workspace garbage collection."""

    def __init__(
        self,
        idle_timeout_seconds: int = DEFAULT_IDLE_SUSPEND_SECONDS,
        stale_reap_days: int = DEFAULT_STALE_REAP_DAYS,
        sweep_interval_seconds: int = SWEEP_INTERVAL_SECONDS,
    ):
        self.idle_timeout_seconds = getattr(settings, "DEV_SANDBOX_IDLE_TIMEOUT_SECONDS", idle_timeout_seconds)
        self.stale_reap_days = getattr(settings, "DEV_SANDBOX_STALE_REAP_DAYS", stale_reap_days)
        self.sweep_interval_seconds = sweep_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background reaper loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="compassx-sandbox-reaper")
        logger.info(
            "Managed Sandbox Reaper started (default_idle_timeout=%ss, default_stale_reap=%sdays, sweep_interval=%ss)",
            self.idle_timeout_seconds,
            self.stale_reap_days,
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
        logger.info("Managed Sandbox Reaper stopped.")

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
                logger.warning("Sandbox reaper sweep encountered an error: %s", e)
            await asyncio.sleep(self.sweep_interval_seconds)

    async def sweep_once(self) -> None:
        """Execute one complete idle and stale sweep."""
        await asyncio.to_thread(self._sync_sweep_idle_workspaces)
        await asyncio.to_thread(self._sync_sweep_stale_workspaces)

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
                    app_cfg = (app.config or {}).get("dev_sandbox", {})
                    auto_suspend_enabled = app_cfg.get("auto_suspend_enabled", True)

                    # If auto-suspend is disabled for this app, do not suspend
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

                    if not ws.last_active_at or ws.last_active_at < cutoff:
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
                                ws.last_active_at.isoformat() if ws.last_active_at else "unknown",
                                idle_timeout_secs,
                            )
                            omnigent_dev_service.suspend_dev_session(app)
        except Exception as err:
            logger.debug("Error during idle sandbox sweep: %s", err)

    def _sync_sweep_stale_workspaces(self) -> None:
        """Identify abandoned workspaces older than stale threshold and clean up disk allocations."""
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

                    app_cfg = (app.config or {}).get("dev_sandbox", {})
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

                    if ws.last_active_at and ws.last_active_at < stale_cutoff:
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


# Global singleton instance
sandbox_reaper_service = SandboxReaperService()
