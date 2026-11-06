from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def restart(self, services: list[str] | None = None) -> PlatformStatus:
    ordered = self._ordered_services(services)
    for launcher, group in self._group_by_launcher(ordered):
        await launcher.restart(group)
    return await self.status(services)
