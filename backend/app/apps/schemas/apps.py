"""CompassX Apps — Pydantic v2 request/response schemas for all §10 API endpoints."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class AppCreate(BaseModel):
    name: str
    catalog_fqn: str                        # catalog.schema.app_name
    workspace_id: uuid.UUID
    versioning_backend: str = "native"      # 'git' | 'native'
    terminal_enabled_prod: bool = False
    max_concurrent_branches: int = 5
    catalog_grants: list[dict[str, Any]] = Field(default_factory=list)
    volume_grants: list[dict[str, Any]] = Field(default_factory=list)


class AppRead(BaseModel):
    app_id: uuid.UUID
    name: str
    catalog_fqn: str
    workspace_id: uuid.UUID
    owner_id: uuid.UUID
    versioning_backend: str
    terminal_enabled_prod: bool
    max_concurrent_branches: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Branch
# ---------------------------------------------------------------------------

class BranchCreate(BaseModel):
    name: str
    from_branch_id: Optional[uuid.UUID] = None  # branch to fork from; None = empty scaffold


class BranchRead(BaseModel):
    branch_id: uuid.UUID
    app_id: uuid.UUID
    name: str
    head_commit_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Checkpoint (commit)
# ---------------------------------------------------------------------------

class CheckpointRequest(BaseModel):
    message: str


class CheckpointResponse(BaseModel):
    commit_id: uuid.UUID
    branch_id: uuid.UUID
    author: str
    message: Optional[str]
    tree_manifest_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

class FileDiff(BaseModel):
    path: str
    status: str     # 'added' | 'modified' | 'deleted'
    diff_lines: Optional[list[str]] = None  # populated only when detail=true query param


class DiffResult(BaseModel):
    commit_a: uuid.UUID
    commit_b: uuid.UUID
    changes: list[FileDiff]


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    commit_id: uuid.UUID
    source_branch_id: uuid.UUID


class PublishResponse(BaseModel):
    app_id: uuid.UUID
    commit_id: uuid.UUID
    production_pod_id: uuid.UUID
    preview_url: str
    status: str


class ProductionStatus(BaseModel):
    app_id: uuid.UUID
    current_commit_id: Optional[uuid.UUID]
    source_branch_id: Optional[uuid.UUID]
    switched_at: Optional[datetime]
    switched_by: Optional[uuid.UUID]
    pod_status: Optional[str]
    preview_url: Optional[str]


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

class FileMeta(BaseModel):
    path: str
    size_bytes: int
    status: str     # 'clean' | 'modified' | 'untracked' | 'deleted'
    last_modified: Optional[datetime] = None


class FileTree(BaseModel):
    files: list[FileMeta]


class FileContent(BaseModel):
    path: str
    content: str    # UTF-8 text; binary files not supported in v1


class FileWrite(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Pod
# ---------------------------------------------------------------------------

class PodRead(BaseModel):
    pod_id: uuid.UUID
    app_id: uuid.UUID
    branch_id: Optional[uuid.UUID]
    pod_kind: str
    k8s_pod_name: str
    preview_url: str
    terminal_enabled: bool
    status: str
    commit_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}
