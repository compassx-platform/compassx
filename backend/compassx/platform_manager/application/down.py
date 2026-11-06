from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def down(self, services: list[str] | None = None) -> None:
    ordered = list(reversed(self._ordered_services(services)))
    for launcher, group in self._group_by_launcher(ordered):
        await launcher.stop(group)
    logger.info("platform: stopped (profile=%s)", self._profile.name)
