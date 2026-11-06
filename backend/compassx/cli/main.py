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



from compassx.cli.application.up import up as up_action
from compassx.cli.application.down import down as down_action
from compassx.cli.application.restart import restart as restart_action
from compassx.cli.application.status import status as status_action
from compassx.cli.application.health import health as health_action
from compassx.cli.application.logs import logs as logs_action
from compassx.cli.application.profile_list import profile_list as profile_list_action
from compassx.cli.application.profile_use import profile_use as profile_use_action

@app.command()
def up(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Do not wait for health checks"),
    timeout: float = typer.Option(300.0, "--timeout", help="Health wait timeout (s)"),
) -> None:
    """Start the platform (or a subset of services)."""
    return up_action(services=services, profile=profile, no_wait=no_wait, timeout=timeout)

@app.command()
def down(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Stop the platform (or a subset of services)."""
    return down_action(services=services, profile=profile)

@app.command()
def restart(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Restart platform services."""
    return restart_action(services=services, profile=profile)

@app.command()
def status(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Show platform service status."""
    return status_action(profile=profile)

@app.command()
def health(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Run health checks with root-cause diagnostics."""
    return health_action(profile=profile)

@app.command()
def logs(
    service: str = typer.Argument(...),
    tail: int = typer.Option(200, "--tail", "-n"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """Show logs for a platform service."""
    return logs_action(service=service, tail=tail, profile=profile)

@profile_app.command("list")
def profile_list() -> None:
    """List available deployment profiles."""
    return profile_list_action()

@profile_app.command("use")
def profile_use(name: str = typer.Argument(...)) -> None:
    """Set the default profile for subsequent commands."""
    return profile_use_action(name=name)

if __name__ == "__main__":
    app()
