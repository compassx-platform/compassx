"""Deployment mode: which platform services start.

Distinct from ServiceMode, which says where one service runs
(local, docker, or kubernetes).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from compassx.models import PlatformError

MODE_ENV_VAR = "COMPASSX_PLATFORM_MODE"
DEFAULT_MODE = "full"
ACTIVE_MODE_FILE = Path(".compassx") / "active-mode"
MODES_FILE = Path(__file__).resolve().parent.parent / "modes.yaml"


@dataclass(frozen=True)
class DeploymentMode:
    """A named subset of platform services.

    ``services is None`` means every service in the active profile.
    """

    name: str
    services: frozenset[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    compose_files: tuple[str, ...] = ()
    description: str = ""

    def includes(self, service: str) -> bool:
        return self.services is None or service in self.services

    def filter(self, names: list[str]) -> list[str]:
        if self.services is None:
            return list(names)
        allowed = self.services
        return [name for name in names if name in allowed]

    def unavailable_reason(self, service: str) -> str:
        return (
            f"{service} is not part of deployment mode '{self.name}'. "
            "Start the full platform with `compassx up --mode full`."
        )


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up to the repo root (contains backend/ and .git)."""
    current = (start or Path(__file__).resolve().parent).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "backend").is_dir() and (candidate / ".git").exists():
            return candidate
    return Path(__file__).resolve().parents[3]


def _read_modes(modes_file: Path) -> dict:
    if not modes_file.exists():
        raise PlatformError(f"Deployment modes file not found at {modes_file}")
    with open(modes_file, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    modes = data.get("modes") or {}
    if not isinstance(modes, dict) or not modes:
        raise PlatformError(f"No deployment modes defined in {modes_file}")
    return modes


def list_modes(modes_file: Path | None = None) -> list[str]:
    return sorted(_read_modes(modes_file or MODES_FILE))


def _parse_mode(name: str, raw: dict | None) -> DeploymentMode:
    raw = raw or {}
    if "services" in raw and raw["services"] is not None:
        services = frozenset(str(item) for item in raw["services"])
    else:
        services = None
    env = {str(key): str(value) for key, value in (raw.get("env") or {}).items()}
    compose_files = tuple(str(item) for item in (raw.get("compose_files") or []))
    return DeploymentMode(
        name=name,
        services=services,
        env=env,
        compose_files=compose_files,
        description=str(raw.get("description") or ""),
    )


def active_mode_name(repo_root: Path | None = None) -> str | None:
    """Return the saved mode name, if the marker file exists and is non-empty."""
    root = repo_root or find_repo_root()
    marker = root / ACTIVE_MODE_FILE
    if not marker.exists():
        return None
    text = marker.read_text(encoding="utf-8").strip()
    return text or None


def resolve_mode_name(
    name: str | None = None,
    *,
    repo_root: Path | None = None,
) -> str:
    """explicit argument > COMPASSX_PLATFORM_MODE > .compassx/active-mode > full."""
    if name:
        return name
    env_name = os.environ.get(MODE_ENV_VAR, "").strip()
    if env_name:
        return env_name
    saved = active_mode_name(repo_root)
    if saved:
        return saved
    return DEFAULT_MODE


def load_deployment_mode(
    name: str | None = None,
    *,
    modes_file: Path | None = None,
    repo_root: Path | None = None,
) -> DeploymentMode:
    path = modes_file or MODES_FILE
    modes = _read_modes(path)
    resolved = resolve_mode_name(name, repo_root=repo_root)
    if resolved not in modes:
        available = ", ".join(sorted(modes)) or "<none>"
        raise PlatformError(
            f"Deployment mode '{resolved}' is not defined. Available: {available}"
        )
    return _parse_mode(resolved, modes[resolved])


def apply_mode_environment(mode: DeploymentMode | None = None, *, repo_root: Path | None = None) -> DeploymentMode:
    """Publish the active mode on the process environment.

    Mode env values win over values already set, so app mode uses local
    storage even when a shell or dotenv file still points at MinIO.
    """
    resolved = mode or load_deployment_mode(repo_root=repo_root)
    os.environ[MODE_ENV_VAR] = resolved.name
    for key, value in resolved.env.items():
        os.environ[key] = value
    return resolved
