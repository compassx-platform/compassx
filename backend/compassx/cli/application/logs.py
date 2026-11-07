from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def logs(
    service: str = typer.Argument(...),
    tail: int = typer.Option(200, "--tail", "-n"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Show logs for a platform service."""
    container = _container(profile, mode)
    try:
        output = asyncio.run(container.platform_manager.logs(service, tail=tail))
    except PlatformError as exc:
        _fail(exc)
        return
    console.print(output or "[dim]<no logs>[/dim]")
