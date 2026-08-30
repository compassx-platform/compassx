"""
Pydantic schemas for the Jobs module API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Task definition (embedded in JobVersion.task_definitions) ─────────────────

class TaskDefinition(BaseModel):
    task_key: str
    name: str
    task_type: str = "notebook"        # notebook | query | dashboard_refresh
    target_ref: Optional[str] = None   # notebook path / query id / dashboard id
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)  # list of task_key strings
    retry_count: Optional[int] = None
    retry_delay_seconds: Optional[int] = None


# ── Retry policy ──────────────────────────────────────────────────────────────

class RetryPolicy(BaseModel):
    retries: int = 0
    retry_delay_seconds: int = 300
    backoff_factor: float = 1.0


# ── Job create / update ───────────────────────────────────────────────────────

class JobCreate(BaseModel):
    name: str
    description: Optional[str] = None
    # No workspace_id: a job is created in the workspace the request is
    # addressed to. Accepting one here let a caller plant a scheduled job in
    # a workspace they have no access to.


class JobUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ── Draft update (saves task + schedule config to draft version) ──────────────

class DraftUpdate(BaseModel):
    schedule_cron: Optional[str] = None
    timezone: str = "UTC"
    max_active_runs: int = 1
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    task_definitions: List[TaskDefinition] = Field(default_factory=list)


# ── Response: Job ─────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    job_id: UUID
    workspace_id: Optional[UUID]
    name: str
    description: Optional[str]
    owner_user_id: Optional[str]
    status: str
    current_version: Optional[int]
    draft_version: Optional[int]
    has_unpublished_changes: bool
    created_at: datetime
    updated_at: datetime

    # Derived from current published version (may be None for brand-new jobs)
    schedule_cron: Optional[str] = None
    timezone: Optional[str] = None
    max_active_runs: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    task_definitions: List[Dict[str, Any]] = Field(default_factory=list)

    # Last-run summary (populated by list endpoint)
    last_run_state: Optional[str] = None
    last_run_started_at: Optional[datetime] = None
    last_run_id: Optional[UUID] = None
    task_count: int = 0
    recent_runs: List[JobRunOut] = Field(default_factory=list)
    publish_state: Optional[str] = None
    airflow_confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Response: JobVersion ──────────────────────────────────────────────────────

class JobVersionOut(BaseModel):
    job_version_id: UUID
    job_id: UUID
    version_number: int
    schedule_cron: Optional[str]
    timezone: str
    max_active_runs: int
    retry_policy: Dict[str, Any]
    task_definitions: List[Dict[str, Any]]
    is_published: bool
    published_at: Optional[datetime]
    published_by: Optional[str]
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


# ── Response: TaskRun ─────────────────────────────────────────────────────────

class TaskRunOut(BaseModel):
    task_run_id: UUID
    job_run_id: UUID
    task_key: str
    try_number: int
    state: str
    execution_ref: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


# ── Response: JobRun ──────────────────────────────────────────────────────────

class JobRunOut(BaseModel):
    job_run_id: UUID
    job_id: UUID
    job_version: Optional[int]
    dag_run_id: Optional[str]
    trigger_type: str
    triggered_by: Optional[str]
    parent_job_run_id: Optional[UUID]
    state: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    last_synced_at: Optional[datetime]
    duration_seconds: Optional[float] = None
    task_runs: List[TaskRunOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ── Run trigger ───────────────────────────────────────────────────────────────

class RunTriggerIn(BaseModel):
    """Optional run-time parameter overrides."""
    parameters: Dict[str, Any] = Field(default_factory=dict)
