from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

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
