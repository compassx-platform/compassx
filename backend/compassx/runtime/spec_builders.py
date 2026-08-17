"""RuntimeSpec builders — factory pattern, one builder per runtime type.

Ported from backend/app/compute/services/runtimes.py, but builders emit
deployment-independent RuntimeSpec objects instead of Kubernetes V1Pod.
Drivers translate specs into pods/containers/processes.

Adding a new runtime type:
1. Subclass BaseSpecBuilder
2. registry.register(MyBuilder())
No Runtime Manager changes required.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from compassx.models import (
    PortMapping,
    ResourceRequirements,
    RuntimeProvisionError,
    RuntimeSpec,
)

logger = logging.getLogger(__name__)

# Runtime image constants (from compute/services/runtimes.py)
SPARK_IMAGE = "apache/spark:3.5.0"
FLINK_IMAGE = "flink:1.18-scala_2.12"
RAY_IMAGE = "rayproject/ray:2.9.0"
DUCKDB_IMAGE = "compassx-compute-duckdb:latest"
NOTEBOOK_JOB_IMAGE = "compassx-airflow-notebook-runner:latest"

DUCKDB_VALID_PROFILES = {"local", "cloud-xs", "cloud-s"}


class BaseSpecBuilder(ABC):
    """Common spec-building helpers shared by all runtime types."""

    runtime_type: str = "abstract"
    default_image: str = ""

    def __init__(
        self,
        *,
        minio_endpoint: str = "minio:9000",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin",
        registry_prefix: str = "",
    ) -> None:
        self._minio_endpoint = minio_endpoint
        self._minio_access_key = minio_access_key
        self._minio_secret_key = minio_secret_key
        self._registry_prefix = registry_prefix

    # ── shared helpers ───────────────────────────────────────────────────

    def _minio_env_vars(self) -> dict[str, str]:
        """MinIO/S3 environment variables injected on every runtime."""
        return {
            "AWS_ENDPOINT_URL": f"http://{self._minio_endpoint}",
            "AWS_ACCESS_KEY_ID": self._minio_access_key,
            "AWS_SECRET_ACCESS_KEY": self._minio_secret_key,
            "AWS_DEFAULT_REGION": "us-east-1",
        }

    def _resolve_image(self, image: str) -> str:
        prefix = self._registry_prefix
        if prefix:
            prefix_clean = prefix.rstrip("/")
            if not image.startswith(prefix_clean):
                return f"{prefix_clean}/{image}"
        return image

    def _standard_labels(
        self, runtime_id: str, user_id: str
    ) -> dict[str, str]:
        return {
            "app": "compassx",
            "runtime": self.runtime_type,
            "user": user_id,
            "compassx/job": runtime_id,
            "compassx/resource": runtime_id,
        }

    def _standard_annotations(self, profile_id: str, env: str) -> dict[str, str]:
        return {
            "compassx/created-at": datetime.now(timezone.utc).isoformat(),
            "compassx/profile": profile_id,
            "compassx/env": env,
        }

    def _resources(self, options: dict[str, Any]) -> ResourceRequirements:
        requests = options.get("requests") or {}
        limits = options.get("limits") or {}
        gpu_raw = limits.get("nvidia.com/gpu", 0)
        return ResourceRequirements(
            cpu_request=requests.get("cpu"),
            memory_request=requests.get("memory"),
            cpu_limit=limits.get("cpu"),
            memory_limit=limits.get("memory"),
            gpu=int(gpu_raw) if gpu_raw else 0,
        )

    # ── per-type hooks ───────────────────────────────────────────────────

    @abstractmethod
    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        """Runtime-type-specific environment variables."""

    def command(self, options: dict[str, Any]) -> list[str]:
        return []

    def ports(self, options: dict[str, Any]) -> list[PortMapping]:
        return []

    def validate(self, options: dict[str, Any]) -> None:
        """Raise RuntimeProvisionError for invalid option combinations."""

    # ── build ────────────────────────────────────────────────────────────

    def build(
        self,
        runtime_id: str,
        *,
        user_id: str = "",
        workspace_id: str = "",
        namespace: str = "",
        env: str = "local",
        options: dict[str, Any] | None = None,
    ) -> RuntimeSpec:
        options = options or {}
        self.validate(options)
        custom_image = options.get("custom_image")
        image = custom_image or self._resolve_image(self.default_image)

        env_vars = {**self._minio_env_vars(), **self.runtime_env(options)}
        extra_env = options.get("extra_env") or {}
        env_vars.update({str(k): str(v) for k, v in extra_env.items()})

        profile_id = options.get("profile_id", "")
        spec = RuntimeSpec(
            runtime_id=runtime_id,
            runtime_type=self.runtime_type,
            container_image=image,
            command=self.command(options),
            resources=self._resources(options),
            env=env_vars,
            ports=self.ports(options),
            labels=self._standard_labels(runtime_id, user_id),
            annotations=self._standard_annotations(profile_id, env),
            namespace=namespace,
            user_id=user_id,
            workspace_id=workspace_id,
            metadata={
                "profile_id": profile_id,
                "env": env,
                "k8s_extra_limits": {
                    k: v
                    for k, v in (options.get("limits") or {}).items()
                    if k not in {"cpu", "memory", "nvidia.com/gpu", "_custom_image"}
                },
            },
        )
        logger.debug(
            "RuntimeSpec built: runtime_id=%s type=%s profile=%s env=%s",
            runtime_id,
            self.runtime_type,
            profile_id,
            env,
        )
        return spec


class SparkSpecBuilder(BaseSpecBuilder):
    runtime_type = "spark"
    default_image = SPARK_IMAGE

    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        limits = options.get("limits") or {}
        return {
            "SPARK_MODE": "master",
            "SPARK_MASTER_URL": "spark://localhost:7077",
            "SPARK_WORKER_MEMORY": limits.get("memory", "1g"),
        }

    def command(self, options: dict[str, Any]) -> list[str]:
        return ["/opt/spark/bin/spark-class", "org.apache.spark.deploy.master.Master"]


class FlinkSpecBuilder(BaseSpecBuilder):
    runtime_type = "flink"
    default_image = FLINK_IMAGE

    @staticmethod
    def _parse_memory_mb(mem_str: str) -> int:
        mem_str = mem_str.strip()
        if mem_str.endswith("Gi"):
            return int(mem_str[:-2]) * 1024
        if mem_str.endswith("Mi"):
            return int(mem_str[:-2])
        if mem_str.endswith(("G", "g")):
            return int(mem_str[:-1]) * 1024
        if mem_str.endswith(("M", "m")):
            return int(mem_str[:-1])
        return 512  # fallback

    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        limits = options.get("limits") or {}
        heap_mb = self._parse_memory_mb(limits.get("memory", "1Gi"))
        return {
            "FLINK_PROPERTIES": (
                f"jobmanager.heap.size: {heap_mb}m\n"
                f"taskmanager.memory.process.size: {heap_mb}m\n"
            )
        }

    def ports(self, options: dict[str, Any]) -> list[PortMapping]:
        return [
            PortMapping(name="rest", container_port=8081),
            PortMapping(name="rpc", container_port=6123),
        ]


class RaySpecBuilder(BaseSpecBuilder):
    runtime_type = "ray"
    default_image = RAY_IMAGE

    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        return {"RAY_DISABLE_MEMORY_MONITOR": "1"}

    def command(self, options: dict[str, Any]) -> list[str]:
        return ["ray", "start", "--head", "--dashboard-host=0.0.0.0"]

    def ports(self, options: dict[str, Any]) -> list[PortMapping]:
        return [
            PortMapping(name="dashboard", container_port=8265),
            PortMapping(name="redis", container_port=6379),
            PortMapping(name="client", container_port=10001),
        ]


class DuckDBSpecBuilder(BaseSpecBuilder):
    """DuckDB runtime — stays alive with a sleep loop; Enterprise Gateway
    execs ipykernel into it on demand."""

    runtime_type = "duckdb"
    default_image = DUCKDB_IMAGE

    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        return {}

    def command(self, options: dict[str, Any]) -> list[str]:
        return ["tail", "-f", "/dev/null"]

    def validate(self, options: dict[str, Any]) -> None:
        profile_id = options.get("profile_id", "")
        if profile_id and profile_id not in DUCKDB_VALID_PROFILES:
            raise RuntimeProvisionError(
                f"DuckDB is only valid with profiles: {', '.join(sorted(DUCKDB_VALID_PROFILES))}"
            )


class NotebookJobSpecBuilder(BaseSpecBuilder):
    """Ephemeral notebook execution runtime selected by the active profile."""

    runtime_type = "notebook-job"
    default_image = NOTEBOOK_JOB_IMAGE

    def runtime_env(self, options: dict[str, Any]) -> dict[str, str]:
        return {}

    def command(self, options: dict[str, Any]) -> list[str]:
        return ["tail", "-f", "/dev/null"]


class SpecBuilderRegistry:
    """Factory registry keyed by runtime type."""

    def __init__(self) -> None:
        self._builders: dict[str, BaseSpecBuilder] = {}

    def register(self, builder: BaseSpecBuilder) -> None:
        self._builders[builder.runtime_type] = builder

    def get(self, runtime_type: str) -> BaseSpecBuilder:
        builder = self._builders.get(runtime_type)
        if builder is None:
            known = ", ".join(sorted(self._builders)) or "<none>"
            raise RuntimeProvisionError(
                f"Unknown runtime type: {runtime_type}. Registered: {known}"
            )
        return builder

    def list_types(self) -> list[str]:
        return sorted(self._builders)


def default_spec_builders(
    *,
    minio_endpoint: str = "minio:9000",
    minio_access_key: str = "minioadmin",
    minio_secret_key: str = "minioadmin",
    registry_prefix: str = "",
) -> SpecBuilderRegistry:
    """Registry pre-populated with the standard CompassX runtime types."""
    kwargs = dict(
        minio_endpoint=minio_endpoint,
        minio_access_key=minio_access_key,
        minio_secret_key=minio_secret_key,
        registry_prefix=registry_prefix,
    )
    registry = SpecBuilderRegistry()
    registry.register(SparkSpecBuilder(**kwargs))
    registry.register(FlinkSpecBuilder(**kwargs))
    registry.register(RaySpecBuilder(**kwargs))
    registry.register(DuckDBSpecBuilder(**kwargs))
    registry.register(NotebookJobSpecBuilder(**kwargs))
    return registry
