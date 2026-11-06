from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def restart(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Restart platform services."""
    container = _container(profile)
    try:
        status = asyncio.run(container.platform_manager.restart(services or None))
    except PlatformError as exc:
        _fail(exc)
        return
    _print_status(status)
