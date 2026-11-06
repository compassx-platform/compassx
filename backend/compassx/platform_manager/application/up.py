from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

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
