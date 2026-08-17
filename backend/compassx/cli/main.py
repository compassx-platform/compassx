"""compassx CLI — platform lifecycle without touching Docker/kubectl/Helm.

Usage:
    compassx up [--profile local-dev] [SERVICES...]
    compassx down [SERVICES...]
    compassx restart [SERVICES...]
    compassx status
    compassx health
    compassx logs SERVICE [--tail 200]
    compassx profile list
    compassx profile use NAME
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from compassx.container import PlatformContainer
from compassx.models import PlatformError
from compassx.registry.profile import PROFILE_ENV_VAR, list_profiles, load_profile


def _profile_names() -> str:
    names = list_profiles()
    return ", ".join(names) if names else "<none>"


app = typer.Typer(
    help=(
        "CompassX platform lifecycle manager\n\n"
        f"Available profiles: {_profile_names()}\n"
        "Use `compassx profile list` to see the active/default profile."
    )
)
profile_app = typer.Typer(help=f"Manage deployment profiles (available: {_profile_names()})")
app.add_typer(profile_app, name="profile")

console = Console()

_ACTIVE_PROFILE_FILE = Path(".compassx") / "active-profile"


def _resolve_profile(profile: str | None) -> str | None:
    if profile:
        return profile
    if os.environ.get(PROFILE_ENV_VAR):
        return None  # load_profile reads the env var
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_PROFILE_FILE
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip() or None
    return None


def _container(profile: str | None) -> PlatformContainer:
    return PlatformContainer(profile_name=_resolve_profile(profile))


def _fail(exc: BaseException) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(code=1)


@app.callback()
def _setup_logging(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def up(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Do not wait for health checks"),
    timeout: float = typer.Option(300.0, "--timeout", help="Health wait timeout (s)"),
) -> None:
    """Start the platform (or a subset of services)."""
    container = _container(profile)
    console.print(f"Starting platform with profile [bold]{container.profile.name}[/bold]...")
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


@app.command()
def down(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Stop the platform (or a subset of services)."""
    container = _container(profile)
    try:
        asyncio.run(container.platform_manager.down(services or None))
    except PlatformError as exc:
        _fail(exc)
        return
    console.print("[green]Platform stopped.[/green]")


@app.command()
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


@app.command()
def status(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Show platform service status."""
    container = _container(profile)
    try:
        result = asyncio.run(container.platform_manager.status())
    except PlatformError as exc:
        _fail(exc)
        return
    _print_status(result)


@app.command()
def health(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Run health checks with root-cause diagnostics."""
    container = _container(profile)
    try:
        report = asyncio.run(container.platform_manager.health())
    except PlatformError as exc:
        _fail(exc)
        return
    table = Table(title=f"Health — profile {container.profile.name}")
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


@app.command()
def logs(
    service: str = typer.Argument(...),
    tail: int = typer.Option(200, "--tail", "-n"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Show logs for a platform service."""
    container = _container(profile)
    try:
        output = asyncio.run(container.platform_manager.logs(service, tail=tail))
    except PlatformError as exc:
        _fail(exc)
        return
    console.print(output or "[dim]<no logs>[/dim]")


@profile_app.command("list")
def profile_list() -> None:
    """List available deployment profiles."""
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_PROFILE_FILE
    active = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    for name in list_profiles():
        prefix = "*" if name == active else " "
        console.print(f"{prefix} {name}")


@profile_app.command("use")
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


def _print_status(status) -> None:
    table = Table(title=f"Platform status — profile {status.profile}")
    table.add_column("Service")
    table.add_column("Running")
    table.add_column("Healthy")
    table.add_column("Detail")
    for s in status.services:
        table.add_row(
            s.name,
            "[green]yes[/green]" if s.running else "[red]no[/red]",
            {True: "[green]yes[/green]", False: "[red]no[/red]", None: "-"}[s.healthy],
            s.detail,
        )
    console.print(table)


if __name__ == "__main__":
    app()
