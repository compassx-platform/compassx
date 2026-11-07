"""compassx CLI — platform lifecycle without touching Docker/kubectl/Helm.

Usage:
    compassx up [--profile local-dev] [--mode full|app] [SERVICES...]
    compassx down [--mode full|app] [SERVICES...]
    compassx restart [--mode full|app] [SERVICES...]
    compassx status [--mode full|app]
    compassx health [--mode full|app]
    compassx logs SERVICE [--tail 200]
    compassx profile list
    compassx profile use NAME
    compassx mode list
    compassx mode use NAME
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
from compassx.registry.deployment_mode import (
    active_mode_name,
    list_modes,
    load_deployment_mode,
)
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
mode_app = typer.Typer(help=f"Manage deployment modes (available: {', '.join(list_modes())})")
app.add_typer(profile_app, name="profile")
app.add_typer(mode_app, name="mode")

console = Console()

_ACTIVE_PROFILE_FILE = Path(".compassx") / "active-profile"
_ACTIVE_MODE_FILE = Path(".compassx") / "active-mode"


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


def _container(profile: str | None, mode: str | None = None) -> PlatformContainer:
    return PlatformContainer(profile_name=_resolve_profile(profile), mode_name=mode)


def _persist_mode(name: str) -> None:
    load_deployment_mode(name)
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_MODE_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(name + "\n", encoding="utf-8")


def _fail(exc: BaseException) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(code=1)


@app.callback()
def _setup_logging(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )





@mode_app.command("list")
def mode_list() -> None:
    """List available deployment modes."""
    container = PlatformContainer()
    marker = container.repo_root / _ACTIVE_MODE_FILE
    active = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    for name in list_modes():
        prefix = "*" if name == active else " "
        console.print(f"{prefix} {name}")


@mode_app.command("use")
def mode_use(name: str = typer.Argument(...)) -> None:
    """Set the default deployment mode for subsequent commands."""
    try:
        _persist_mode(name)
    except PlatformError as exc:
        _fail(exc)
        return
    console.print(f"Active mode set to [bold]{name}[/bold]")


def _print_status(status) -> None:
    mode = getattr(status, "mode", "full")
    table = Table(title=f"Platform status — profile {status.profile} — mode {mode}")
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
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Do not wait for health checks"),
    timeout: float = typer.Option(300.0, "--timeout", help="Health wait timeout (s)"),
) -> None:
    """Start the platform (or a subset of services)."""
    return up_action(services=services, profile=profile, mode=mode, no_wait=no_wait, timeout=timeout)

@app.command()
def down(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Stop the platform (or a subset of services)."""
    return down_action(services=services, profile=profile, mode=mode)

@app.command()
def restart(
    services: Optional[List[str]] = typer.Argument(None),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Restart platform services."""
    return restart_action(services=services, profile=profile, mode=mode)

@app.command()
def status(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Show platform service status."""
    return status_action(profile=profile, mode=mode)

@app.command()
def health(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Run health checks with root-cause diagnostics."""
    return health_action(profile=profile, mode=mode)

@app.command()
def logs(
    service: str = typer.Argument(...),
    tail: int = typer.Option(200, "--tail", "-n"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Deployment mode: full or app"),
) -> None:
    """Show logs for a platform service."""
    return logs_action(service=service, tail=tail, profile=profile, mode=mode)

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
