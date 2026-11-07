"""Docker Compose Launcher — platform services via `docker compose`.

Wraps the compose CLI (v2). Surfaces stderr on failure with actionable
root-cause messages instead of raw CalledProcessError.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from compassx.interfaces.launcher import Launcher, LauncherStatus, ServiceStatus
from compassx.models import LauncherError
from compassx.registry.deployment_mode import DeploymentMode
from compassx.registry.profile import DeploymentProfile

logger = logging.getLogger(__name__)

# Platform service name -> compose service names. Services not listed map 1:1.
# Empty list = no dedicated container (served by another container).
COMPOSE_SERVICE_MAP: dict[str, list[str]] = {
    "airflow": [
        "jobs-runner-image",
        "airflow-init",
        "airflow-webserver",
        "airflow-scheduler",
    ],
    "mlflow": ["mlflow-init", "mlflow"],
    "minio-console": [],        # same container as minio
    "jupyter-server": [],       # served via enterprise-gateway/notebook flow
}

# Custom images built on demand. An image is built only when one of its
# platform services is actually being started.
_IMAGE_SPECS: tuple[tuple[str, str, float, frozenset[str]], ...] = (
    ("compassx-enterprise-gateway:latest", "Dockerfile.eg", 2.5, frozenset({"enterprise-gateway"})),
    ("compassx-airflow-notebook-runner:latest", "Dockerfile.airflow-notebook", 2.0, frozenset({"airflow"})),
    ("compassx-compute-duckdb:latest", "Dockerfile.compute-duckdb", 1.5, frozenset({"enterprise-gateway"})),
    ("compassx-jupyter-server:latest", "Dockerfile.jupyter-server", 1.5, frozenset({"jupyter-server", "enterprise-gateway"})),
)


def images_for_services(services: list[str]) -> list[tuple[str, str, float]]:
    """Return (tag, dockerfile, estimate minutes) for images the services need."""
    requested = set(services)
    return [
        (tag, dockerfile, estimate)
        for tag, dockerfile, estimate, owners in _IMAGE_SPECS
        if owners & requested
    ]


def _to_compose_services(services: list[str]) -> list[str]:
    result: list[str] = []
    for service in services:
        mapped = COMPOSE_SERVICE_MAP.get(service, [service])
        result.extend(m for m in mapped if m not in result)
    return result


class DockerComposeLauncher(Launcher):
    name = "docker"

    def __init__(
        self,
        profile: DeploymentProfile,
        repo_root: Path,
        deployment_mode: DeploymentMode | None = None,
    ) -> None:
        self._profile = profile
        self._repo_root = repo_root
        self._backend_dir = repo_root / "backend"
        files = list(profile.compose_files or ([profile.compose_file] if profile.compose_file else []))
        if deployment_mode is not None:
            files.extend(deployment_mode.compose_files)
        self._compose_files = [repo_root / f for f in files]
        self._compose_file = (
            self._compose_files[0]
            if self._compose_files
            else repo_root / "deployments/docker-compose/docker-compose.yml"
        )
        self._project = profile.compose_project

    def _base_cmd(self) -> list[str]:
        cmd = ["docker", "compose"]
        for f in self._compose_files:
            cmd.extend(["-f", str(f)])
        cmd.extend([
            "-p",
            self._project,
            # Enable all compose profiles; service selection is explicit.
            "--profile",
            "full",
        ])
        return cmd

    async def _image_exists(self, tag: str) -> bool:
        result = await asyncio.to_thread(
            subprocess.run, ["docker", "image", "inspect", tag], capture_output=True, text=True
        )
        return result.returncode == 0

    async def ensure_images(self, services: list[str] | None = None) -> None:
        """Build custom Docker images the requested services need, if missing."""
        selected = images_for_services(services or [])
        if not selected:
            logger.info("docker-launcher: no custom images required for this mode")
            return
        images = [
            (tag, dockerfile, self._backend_dir, est_min)
            for tag, dockerfile, est_min in selected
        ]

        missing = []
        for tag, dockerfile, context_dir, est_min in images:
            if await self._image_exists(tag):
                logger.info("docker-launcher: image %s available, skip", tag)
            else:
                missing.append((tag, dockerfile, context_dir, est_min))

        if not missing:
            logger.info("docker-launcher: all required images are cached/available")
            return

        from rich.console import Console
        from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

        console = Console()
        total_est = sum(item[3] for item in missing)
        console.print(f"[cyan]Preparing Docker images[/cyan] (estimated {total_est:.1f} min total)")
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("{task.completed}/{task.total} steps"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for tag, dockerfile, context_dir, est_min in missing:
                task = progress.add_task(f"{tag} [{est_min:.1f} min est.]", total=1)
                path = context_dir / dockerfile
                if not path.exists():
                    raise LauncherError(f"Dockerfile not found: {path}")
                logger.info("docker-launcher: building %s from %s", tag, path)
                progress.update(task, advance=0, description=f"{tag} building...")
                cmd = ["docker", "build", "-f", dockerfile, "-t", tag, "."]
                result = await asyncio.to_thread(
                    subprocess.run, cmd, cwd=str(context_dir), capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise LauncherError(
                        f"Failed to build Docker image {tag}: {result.stderr or result.stdout}"
                    )
                progress.update(task, completed=1, description=f"{tag} done")

    async def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
        for f in self._compose_files:
            if not f.exists():
                raise LauncherError(
                    f"Compose file not found: {f}. "
                    f"Check docker.compose_file in profile '{self._profile.name}'."
                )
        cmd = self._base_cmd() + args
        logger.info("compose: %s", " ".join(cmd))
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True
        )
        if check and result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise LauncherError(self._diagnose(args, result.returncode, stderr))
        return result

    @staticmethod
    def _diagnose(args: list[str], rc: int, stderr: str) -> str:
        lowered = stderr.lower()
        if "cannot connect to the docker daemon" in lowered or "docker daemon" in lowered:
            return (
                "Docker daemon is not running. Start Docker Desktop (or dockerd) "
                f"and retry. (docker compose {' '.join(args)} rc={rc})"
            )
        if "port is already allocated" in lowered or "address already in use" in lowered:
            return (
                "A required port is already in use by another process. Stop the "
                f"conflicting process or change the port mapping. Details: {stderr}"
            )
        if "no such service" in lowered:
            return (
                f"Unknown compose service. Check service names in the compose file. "
                f"Details: {stderr}"
            )
        if "pull access denied" in lowered or "manifest unknown" in lowered:
            return (
                f"Image could not be pulled (missing image or no registry access). "
                f"Details: {stderr}"
            )
        return f"docker compose {' '.join(args)} failed (rc={rc}): {stderr or '<no stderr>'}"

    async def start(self, services: list[str]) -> None:
        if self._profile.docker_ensure_images:
            await self.ensure_images(services)
        targets = _to_compose_services(services)
        if not targets:
            return
        await self._run(["up", "-d", "--wait", *targets])
        logger.info("compose: services up: %s", ", ".join(targets))

    async def stop(self, services: list[str]) -> None:
        targets = _to_compose_services(services)
        if not targets:
            return
        await self._run(["stop", *targets])
        logger.info("compose: services stopped: %s", ", ".join(targets))

    async def restart(self, services: list[str]) -> None:
        targets = _to_compose_services(services)
        if targets:
            await self._run(["restart", *targets])

    async def status(self, services: list[str]) -> LauncherStatus:
        result = await self._run(["ps", "--format", "json", "--all"], check=False)
        state_by_service: dict[str, dict] = {}
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            state_by_service[item.get("Service", "")] = item

        statuses = []
        for service in services:
            compose_names = COMPOSE_SERVICE_MAP.get(service, [service])
            if not compose_names:
                continue  # no dedicated container
            item = state_by_service.get(compose_names[0])
            if item is None:
                statuses.append(
                    ServiceStatus(name=service, running=False, detail="not created")
                )
                continue
            state = (item.get("State") or "").lower()
            health = (item.get("Health") or "").lower()
            running = state == "running"
            healthy = None
            if health:
                healthy = health == "healthy"
            statuses.append(
                ServiceStatus(
                    name=service,
                    running=running,
                    healthy=healthy,
                    detail=f"state={state}" + (f" health={health}" if health else ""),
                )
            )
        return LauncherStatus(launcher=self.name, services=statuses)

    async def logs(self, service: str, tail: int = 200) -> str:
        targets = COMPOSE_SERVICE_MAP.get(service, [service])
        if not targets:
            return ""
        result = await self._run(
            ["logs", "--no-color", "--tail", str(tail), targets[0]], check=False
        )
        return result.stdout or result.stderr or ""
