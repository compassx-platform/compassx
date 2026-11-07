from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def status(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Show platform service status."""
    container = _container(profile, mode)
    try:
        result = asyncio.run(container.platform_manager.status())
    except PlatformError as exc:
        _fail(exc)
        return
    _print_status(result)
