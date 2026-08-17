"""Pydantic models for the compute module."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RuntimeType(str, Enum):
    SPARK = "spark"
    FLINK = "flink"
    RAY = "ray"
    DUCKDB = "duckdb"


class ComputeProfileId(str, Enum):
    LOCAL = "local"
    CLOUD_XS = "cloud-xs"
    CLOUD_S = "cloud-s"
    CLOUD_L = "cloud-l"
    GPU = "gpu"


class JobResponse(BaseModel):
    job_id: str
    pod_name: str
    namespace: str
    runtime: str
    profile: str
    status: str
    created_at: datetime


class JobStatus(BaseModel):
    job_id: str
    pod_name: str
    phase: str  # Pending | Running | Succeeded | Failed | Unknown
    runtime: str
    profile: str
    user_id: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None  # failure reason if failed


class ComputeProfileInfo(BaseModel):
    id: str
    label: str
    description: str
    available: bool
    reason: str | None = None
    resources: dict


class ComputeResourceRequest(BaseModel):
    """Request to create a persistent compute resource."""
    name: str
    runtime: RuntimeType
    profile: ComputeProfileId
    description: str | None = None
    custom_image: str | None = None
    extra_env: dict[str, str] | None = None


class ComputeResourceResponse(BaseModel):
    """Response for compute resource."""
    id: str
    name: str
    runtime: str
    profile: str
    user_id: str
    created_by: str
    created_at: datetime
    description: str | None = None
    deployment_name: str | None = None
    desired_status: str = "stopped"
    is_default: bool = False


class ComputeResourceStatus(BaseModel):
    """Status of a compute resource including runtime info."""
    id: str
    name: str
    runtime: str
    profile: str
    user_id: str
    created_by: str
    created_at: datetime
    description: str | None = None
    job_id: str | None = None
    deployment_name: str | None = None
    desired_status: str = "stopped"
    is_default: bool = False
    # Stable platform runtime ID (use this; pod_name is deprecated).
    runtime_id: str | None = None
    # DEPRECATED: infrastructure detail — will be removed. Use runtime_id.
    pod_name: str | None = None
    phase: str | None = None  # Pending | Running | Succeeded | Failed | Unknown
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None


class ComputeServiceInfo(BaseModel):
    """Service status shown in the compute module."""

    id: str
    label: str
    phase: str
    message: str = ""
    details: dict = Field(default_factory=dict)
