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
from compassx.models import PlatformError, ServiceMode
from compassx.platform_manager.health import HealthChecker, HealthReport
from compassx.registry.deployment_mode import DeploymentMode
from compassx.registry.profile import DeploymentProfile

logger = logging.getLogger(__name__)


@dataclass
class PlatformStatus:
    profile: str
    mode: str = "full"
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
        deployment_mode: DeploymentMode | None = None,
    ) -> None:
        self._profile = profile
        self._launchers = launchers
        self._health = health_checker
        # Callers that omit a mode start every profile service. The container
        # passes the resolved mode so CLI runs honor --mode / the saved marker.
        self._mode = deployment_mode or DeploymentMode(name="full")

    @property
    def profile(self) -> DeploymentProfile:
        return self._profile

    # ── helpers ──────────────────────────────────────────────────────────

    def _ordered_services(self, services: list[str] | None = None) -> list[str]:
        known = list(self._profile.services)
        order = [s for s in self._profile.startup_order if s in known]
        # Any profile services not in startup_order are appended at the end.
        order += [s for s in known if s not in order]
        order = self._mode.filter(order)
        if services:
            unknown = [s for s in services if s not in known]
            if unknown:
                raise PlatformError(
                    f"Unknown service(s): {', '.join(unknown)}. "
                    f"Known: {', '.join(known)}"
                )
            excluded = [s for s in services if not self._mode.includes(s)]
            if excluded:
                raise PlatformError(
                    f"Service(s) {', '.join(excluded)} are not part of deployment "
                    f"mode '{self._mode.name}'. Use --mode full to start them."
                )
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
        from compassx.platform_manager.application.up import up as up_action
        return await up_action(self, services=services, wait_healthy=wait_healthy, health_timeout=health_timeout)

    async def down(self, services: list[str] | None = None) -> None:
        from compassx.platform_manager.application.down import down as down_action
        return await down_action(self, services=services)

    async def restart(self, services: list[str] | None = None) -> PlatformStatus:
        from compassx.platform_manager.application.restart import restart as restart_action
        return await restart_action(self, services=services)

    async def status(
        self, services: list[str] | None = None, *, health: HealthReport | None = None
    ) -> PlatformStatus:
        from compassx.platform_manager.application.status import status as status_action
        return await status_action(self, services=services, health=health)

    async def health(self, services: list[str] | None = None) -> HealthReport:
        from compassx.platform_manager.application.health import health as health_action
        return await health_action(self, services=services)

    async def logs(self, service: str, tail: int = 200) -> str:
        from compassx.platform_manager.application.logs import logs as logs_action
        return await logs_action(self, service=service, tail=tail)
