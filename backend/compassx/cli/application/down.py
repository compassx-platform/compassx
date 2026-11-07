from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def down(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Stop the platform (or a subset of services)."""
    container = _container(profile, mode)
    try:
        asyncio.run(container.platform_manager.down(services or None))
    except PlatformError as exc:
        _fail(exc)
        return
    console.print("[green]Platform stopped.[/green]")
