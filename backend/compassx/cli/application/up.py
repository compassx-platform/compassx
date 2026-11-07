from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def up(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Do not wait for health checks"),
    timeout: float = typer.Option(300.0, "--timeout", help="Health wait timeout (s)"),
) -> None:
    """Start the platform (or a subset of services)."""
    previous_mode = None
    if mode:
        root = PlatformContainer().repo_root
        previous_mode = active_mode_name(root) or "full"
        _persist_mode(mode)
    container = _container(profile, mode)
    if mode and not services and previous_mode != container.deployment_mode.name:
        asyncio.run(container.platform_manager.down(["backend", "frontend"]))
    console.print(
        f"Starting platform with profile [bold]{container.profile.name}[/bold] "
        f"mode [bold]{container.deployment_mode.name}[/bold]..."
    )
    try:
        status = asyncio.run(
            container.platform_manager.up(
                services or None, wait_healthy=not no_wait, health_timeout=timeout
            )
        )
    except PlatformError as exc:
        _fail(exc)
        return
    _print_status(status)
    console.print("[green]Platform ready.[/green]" if status.ready else "[yellow]Platform started (some services not running).[/yellow]")
