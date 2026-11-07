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
from compassx.registry.deployment_mode import active_mode_name, load_deployment_mode
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


_ACTIVE_MODE_FILE = Path(".compassx") / "active-mode"


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


