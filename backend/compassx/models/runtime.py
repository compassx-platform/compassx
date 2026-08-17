from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class RuntimePhase(str, Enum):
    """Explicit runtime lifecycle states."""

    CREATING = "creating"
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ResourceRequirements:
    """CPU/memory/GPU requests and limits (Kubernetes-style strings)."""

    cpu_request: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_request: Optional[str] = None
    memory_limit: Optional[str] = None
    gpu: int = 0


@dataclass(frozen=True)
class VolumeMount:
    name: str
    mount_path: str
    host_path: Optional[str] = None
    claim_name: Optional[str] = None
    read_only: bool = False


@dataclass(frozen=True)
class PortMapping:
    name: str
    container_port: int
    host_port: Optional[int] = None
    protocol: str = "TCP"


@dataclass
class RuntimeSpec:
    """Deployment-independent description of a user execution runtime.

    The Runtime Manager builds these from business requests; drivers
    translate them into pods, containers, or local processes.
    """

    runtime_id: str
    runtime_type: str
    container_image: str = ""
    command: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    resources: ResourceRequirements = field(default_factory=ResourceRequirements)
    env: dict[str, str] = field(default_factory=dict)
    ports: list[PortMapping] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    namespace: str = ""
    working_dir: str = ""
    user_id: str = ""
    workspace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Label applied to every infrastructure resource so drivers can rediscover
# the underlying pod/container from the stable runtime ID.
RUNTIME_ID_LABEL = "compassx/runtime-id"
RUNTIME_TYPE_LABEL = "compassx/runtime-type"
MANAGED_BY_LABEL = "compassx/managed-by"
MANAGED_BY_VALUE = "compassx-platform"


@dataclass
class RuntimeInfo:
    """Current state of a runtime as reported by a driver.

    ``infra_id`` (pod name / container id / PID) is internal to the
    Resource Manager and must never be exposed through public APIs.
    """

    runtime_id: str
    phase: RuntimePhase
    runtime_type: str = ""
    infra_id: str = ""
    message: str = ""
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
