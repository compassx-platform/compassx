from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def profile_list() -> None:
    """List available deployment profiles."""
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_PROFILE_FILE
    active = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    for name in list_profiles():
        prefix = "*" if name == active else " "
        console.print(f"{prefix} {name}")
