from __future__ import annotations

from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class WorkspaceIdentityInfo(BaseModel):
    identity_id: str
    principal_type: str = "app_workload"
    role: str = "app_executor"
    scopes: list[str] = ["catalog:read", "compute:run", "models:inference"]
    created_at: Optional[str] = None


class AppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    app_type: str = "streamlit"
    route: Optional[str] = None
    slug: Optional[str] = None

    # Git Configuration
    git_provider: str = "github"
    git_repo_url: str = Field(..., min_length=1)
    git_ref: str = "main"
    git_ref_type: str = "branch"
    git_branch: Optional[str] = None
    git_subdir: Optional[str] = None
    entrypoint: Optional[str] = None

    # Git Credentials (Link Git Account or PAT)
    git_credential_type: str = "none"  # link_account, pat, none
    git_credential_nickname: Optional[str] = None
    git_connection_id: Optional[int] = None
    git_pat: Optional[str] = None

    config: Optional[Dict[str, Any]] = None


class AppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    app_type: Optional[str] = None
    status: Optional[str] = None
    route: Optional[str] = None

    git_provider: Optional[str] = None
    git_repo_url: Optional[str] = None
    git_ref: Optional[str] = None
    git_ref_type: Optional[str] = None
    git_branch: Optional[str] = None
    git_subdir: Optional[str] = None
    entrypoint: Optional[str] = None

    git_credential_type: Optional[str] = None
    git_credential_nickname: Optional[str] = None
    git_connection_id: Optional[int] = None
    git_pat: Optional[str] = None

    config: Optional[Dict[str, Any]] = None


class AppResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_slug: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    app_type: str
    status: str
    route: str

    git_provider: str
    git_repo_url: str
    git_ref: str
    git_ref_type: str
    git_branch: str
    git_subdir: Optional[str] = None
    entrypoint: Optional[str] = None

    git_credential_type: str
    git_credential_nickname: Optional[str] = None
    git_connection_id: Optional[int] = None
    pat_configured: bool = False

    workspace_identity: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppDeployResponse(BaseModel):
    deployment_id: str
    app_id: str
    status: str
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    git_ref: str
    duration_seconds: Optional[float] = None
    triggered_by: Optional[str] = None
    created_at: str
    logs: list[str] = []


class AppLogsResponse(BaseModel):
    app_id: str
    status: str
    logs: list[str] = []
