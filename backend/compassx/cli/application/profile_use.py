from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def profile_use(name: str = typer.Argument(...)) -> None:
    """Set the default profile for subsequent commands."""
    try:
        load_profile(name)  # validate
    except PlatformError as exc:
        _fail(exc)
        return
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_PROFILE_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(name, encoding="utf-8")
    console.print(f"Active profile set to [bold]{name}[/bold]")
