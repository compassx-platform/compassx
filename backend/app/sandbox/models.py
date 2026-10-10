"""Data models and schemas for the centralized Sandbox Module."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SandboxStatus(str, Enum):
    """Lifecycle status of a Sandbox."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    SUSPENDED = "suspended"
    FAILED = "failed"
    TERMINATED = "terminated"


class StorageMount(BaseModel):
    """Host or volume storage mount specification."""
    source_path: str = Field(description="Host path or named volume to mount")
    mount_path: str = Field(description="Path inside the sandbox container/pod")
    read_only: bool = Field(default=False, description="Whether the mount is read-only")


class InitScript(BaseModel):
    """Startup initialization script or command executed once the sandbox is provisioned."""
    name: str = Field(description="Human-readable label for the init step")
    command: Any = Field(description="Command string or list of argument tokens to execute")
    working_dir: Optional[str] = Field(default=None, description="Working directory inside sandbox")
    timeout_seconds: int = Field(default=600, description="Max execution timeout in seconds")
    ignore_failure: bool = Field(default=False, description="Continue provisioning if this script fails")
    env: Dict[str, str] = Field(default_factory=dict, description="Custom environment variables for this script")


class SandboxProgress(BaseModel):
    """Detailed stage progression and status tracking during sandbox lifecycle."""
    stage: str = Field(default="pending", description="'checking', 'allocating', 'starting', 'initializing', 'ready', 'failed'")
    step_index: int = Field(default=0, description="1-based index of currently executing step")
    total_steps: int = Field(default=0, description="Total number of steps in provisioning pipeline")
    step_name: str = Field(default="", description="Name/title of the current step")
    message: str = Field(default="", description="Human-readable progress message")
    percent: int = Field(default=0, description="Progress percentage (0 to 100)")
    elapsed_seconds: float = Field(default=0.0, description="Seconds elapsed since provisioning started")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional context or step stdout")


class SandboxSpec(BaseModel):
    """Declarative specification for provisioning an isolated compute sandbox."""
    sandbox_id: Optional[str] = Field(default=None, description="Unique sandbox ID (auto-generated if omitted)")
    consumer_key: Optional[str] = Field(
        default=None,
        description="Deterministic consumer identifier (e.g. 'app_123', 'agent_456') for deduplication & idempotency"
    )
    name: str = Field(description="Human-readable name of the sandbox")
    consumer_module: str = Field(
        default="generic",
        description="The consumer module requesting this sandbox (e.g., 'app', 'agent', 'notebook', 'job', 'omnigent', 'custom')"
    )
    workspace_id: Optional[str] = Field(default=None, description="CompassX workspace ID")
    runtime_mode: Optional[str] = Field(
        default=None,
        description="Runtime driver override ('docker', 'kubernetes', 'local'). If None, resolved from active profile."
    )
    image: Optional[str] = Field(
        default=None,
        description="Container image to run (e.g., 'python:3.11-slim', 'node:20', 'compassx/runtime-base:latest')"
    )
    cpu_limit: Optional[str] = Field(default=None, description="CPU resource limit (e.g. '2.0' or '2000m')")
    memory_limit: Optional[str] = Field(default=None, description="Memory resource limit (e.g. '2Gi' or '4Gi')")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables injected into the sandbox")
    storage_mounts: List[StorageMount] = Field(default_factory=list, description="Volume/path mounts")
    ports: List[int] = Field(default_factory=list, description="Network ports to expose (e.g. [8080, 8501, 3000])")
    init_scripts: List[InitScript] = Field(
        default_factory=list,
        description="Sequential init scripts to run after compute starts to make the sandbox ready"
    )
    working_dir: Optional[str] = Field(default="/workspace", description="Default working directory inside sandbox")
    labels: Dict[str, str] = Field(default_factory=dict, description="Metadata labels for tracking and filtering")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom module metadata")
    idle_timeout_seconds: Optional[int] = Field(
        default=None,
        description="Idle timeout in seconds before auto-suspending (defaults to profile policy)"
    )


class ExecResult(BaseModel):
    """Execution output from running a command inside a sandbox."""
    exit_code: int = Field(default=0, description="Process exit code")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    success: bool = Field(default=True, description="True if exit_code == 0")


class SandboxInstance(BaseModel):
    """Runtime representation and state of a provisioned sandbox."""
    id: str = Field(description="Unique identifier for the sandbox")
    consumer_key: Optional[str] = Field(default=None, description="Deterministic key for idempotency")
    name: str = Field(description="Human-readable sandbox name")
    consumer_module: str = Field(description="Module that requested this sandbox")
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID")
    status: SandboxStatus = Field(default=SandboxStatus.PENDING, description="Current lifecycle state")
    runtime_mode: str = Field(description="Driver used: 'docker', 'kubernetes', or 'local'")
    image: Optional[str] = Field(default=None, description="Active container image")
    container_id: Optional[str] = Field(default=None, description="Docker container ID if running in Docker")
    pod_name: Optional[str] = Field(default=None, description="Kubernetes Pod name if running in K8s")
    endpoints: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of port/service name to reachable URL (e.g. {'8080': 'http://localhost:8080'})"
    )
    ports: List[int] = Field(default_factory=list, description="Exposed port numbers")
    working_dir: str = Field(default="/workspace", description="Working directory inside sandbox")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Creation timestamp"
    )
    started_at: Optional[str] = Field(default=None, description="Startup timestamp")
    stopped_at: Optional[str] = Field(default=None, description="Stop/termination timestamp")
    labels: Dict[str, str] = Field(default_factory=dict, description="Labels associated with the sandbox")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata attributes")
    progress: Optional[SandboxProgress] = Field(default=None, description="Current stage and step progress")
    error_message: Optional[str] = Field(default=None, description="Error explanation if status is FAILED")

