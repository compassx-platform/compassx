from __future__ import annotations

def _bind():
    import compassx.platform_manager.application.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

async def logs(self, service: str, tail: int = 200) -> str:
    mode = self._profile.mode_for(service)
    launcher = self._launchers.get(mode)
    if launcher is None:
        from compassx.models import LauncherError

        raise LauncherError(
            f"No launcher available for mode '{mode.value}' (service '{service}')"
        )
    return await launcher.logs(service, tail=tail)
