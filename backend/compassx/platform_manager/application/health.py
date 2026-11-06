from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def health(self, services: list[str] | None = None) -> HealthReport:
    targets = services or self._ordered_services()
    return await self._health.check_all(targets)
