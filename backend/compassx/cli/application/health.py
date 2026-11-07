from __future__ import annotations

def _bind():
    import compassx.cli.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def health(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Run health checks with root-cause diagnostics."""
    container = _container(profile, mode)
    try:
        report = asyncio.run(container.platform_manager.health())
    except PlatformError as exc:
        _fail(exc)
        return
    table = Table(
        title=f"Health — profile {container.profile.name} — mode {container.deployment_mode.name}"
    )
    table.add_column("Service")
    table.add_column("Endpoint")
    table.add_column("Status")
    table.add_column("Latency")
    table.add_column("Root cause")
    for s in report.services:
        table.add_row(
            s.name,
            s.endpoint,
            "[green]healthy[/green]" if s.healthy else f"[red]{s.cause or 'down'}[/red]",
            f"{s.latency_ms}ms" if s.latency_ms is not None else "-",
            s.message or "-",
        )
    console.print(table)
    raise typer.Exit(code=0 if report.all_healthy else 1)
