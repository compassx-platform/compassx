from __future__ import annotations


def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def mode_use(name: str = typer.Argument(...)) -> None:
    """Set the default deployment mode for subsequent commands."""
    try:
        _persist_mode(name)
    except PlatformError as exc:
        _fail(exc)
        return
    console.print(f"Active mode set to [bold]{name}[/bold]")
