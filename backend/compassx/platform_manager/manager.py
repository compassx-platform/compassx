"""Platform Manager — deployment-independent platform lifecycle.

Startup sequence (per spec):
1. Load deployment profile
2. Determine mode per service
3. Select launcher per service
4. Start services in startup_order
5. Wait until required services pass health checks
6. Platform Ready
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from compassx.interfaces.launcher import Launcher, ServiceStatus
from compassx.models import ServiceMode
from compassx.platform_manager.health import HealthChecker, HealthReport
from compassx.registry.profile import DeploymentProfile

logger = logging.getLogger(__name__)


@dataclass
class PlatformStatus:
    profile: str
    services: list[ServiceStatus] = field(default_factory=list)
    health: HealthReport | None = None

    @property
    def ready(self) -> bool:
        return bool(self.services) and all(s.running for s in self.services)


class PlatformManager:
    def __init__(
        self,
        profile: DeploymentProfile,
        launchers: dict[ServiceMode, Launcher],
        health_checker: HealthChecker,
    ) -> None:
        self._profile = profile
        self._launchers = launchers
        self._health = health_checker

    @property
    def profile(self) -> DeploymentProfile:
        return self._profile

    # ── helpers ──────────────────────────────────────────────────────────

    def _ordered_services(self, services: list[str] | None = None) -> list[str]:
        known = list(self._profile.services)
        order = [s for s in self._profile.startup_order if s in known]
        # Any profile services not in startup_order are appended at the end.
        order += [s for s in known if s not in order]
        if services:
            order = [s for s in order if s in services]
        return order

    def _group_by_launcher(self, services: list[str]) -> list[tuple[Launcher, list[str]]]:
        """Group consecutive services by launcher, preserving startup order."""
        groups: list[tuple[Launcher, list[str]]] = []
        for service in services:
            mode = self._profile.mode_for(service)
            launcher = self._launchers.get(mode)
            if launcher is None:
                logger.warning(
                    "platform: no launcher for mode '%s' (service %s); skipping",
                    mode.value,
                    service,
                )
                continue
            if groups and groups[-1][0] is launcher:
                groups[-1][1].append(service)
            else:
                groups.append((launcher, [service]))
        return groups

    # ── lifecycle ────────────────────────────────────────────────────────

    async def up(
        self,
        services: list[str] | None = None,
        *,
        wait_healthy: bool = True,
        health_timeout: float = 300.0,
    ) -> PlatformStatus:
        ordered = self._ordered_services(services)
        logger.info(
            "platform: starting profile=%s services=%s",
            self._profile.name,
            ", ".join(ordered),
        )
        for launcher, group in self._group_by_launcher(ordered):
            await launcher.start(group)

        health = None
        if wait_healthy:
            required = [
                s for s in self._profile.required_healthy if s in ordered
            ] or ordered
            health = await self._health.wait_until_healthy(
                required, timeout=health_timeout
            )
            logger.info("platform: READY (profile=%s)", self._profile.name)
        return await self.status(services, health=health)

    async def down(self, services: list[str] | None = None) -> None:
        ordered = list(reversed(self._ordered_services(services)))
        for launcher, group in self._group_by_launcher(ordered):
            await launcher.stop(group)
        logger.info("platform: stopped (profile=%s)", self._profile.name)

    async def restart(self, services: list[str] | None = None) -> PlatformStatus:
        ordered = self._ordered_services(services)
        for launcher, group in self._group_by_launcher(ordered):
            await launcher.restart(group)
        return await self.status(services)

    async def status(
        self, services: list[str] | None = None, *, health: HealthReport | None = None
    ) -> PlatformStatus:
        ordered = self._ordered_services(services)
        statuses: list[ServiceStatus] = []
        for launcher, group in self._group_by_launcher(ordered):
            launcher_status = await launcher.status(group)
            statuses.extend(launcher_status.services)
        return PlatformStatus(
            profile=self._profile.name, services=statuses, health=health
        )

    async def health(self, services: list[str] | None = None) -> HealthReport:
        targets = services or self._ordered_services()
        return await self._health.check_all(targets)

    async def logs(self, service: str, tail: int = 200) -> str:
        mode = self._profile.mode_for(service)
        launcher = self._launchers.get(mode)
        if launcher is None:
            from compassx.models import LauncherError

            raise LauncherError(
                f"No launcher available for mode '{mode.value}' (service '{service}')"
            )
        return await launcher.logs(service, tail=tail)
