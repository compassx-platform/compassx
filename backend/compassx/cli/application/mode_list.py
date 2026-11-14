from __future__ import annotations


def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def mode_list() -> None:
    """List available deployment modes."""
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_MODE_FILE
    active = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    for name in list_modes():
        prefix = "*" if name == active else " "
        console.print(f"{prefix} {name}")
