from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import SystemBase


class App(SystemBase):
    """Application model stored in the system database under the 'apps' schema.
    
    Each application is strictly workspace-scoped with an assigned Workspace Identity.
    """
    __tablename__ = "apps"
    __table_args__ = {"schema": "apps"}

    id = Column(String(64), primary_key=True, default=lambda: f"app_{uuid.uuid4().hex[:16]}")
    workspace_id = Column(String(64), nullable=False, index=True)
    workspace_slug = Column(String(128), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    app_type = Column(String(64), nullable=False, default="streamlit")
    status = Column(String(32), nullable=False, default="active")
    route = Column(String(255), nullable=False)

    # Git Repository Details
    git_provider = Column(String(64), nullable=False, default="github")
    git_repo_url = Column(String(512), nullable=False)
    git_ref = Column(String(128), nullable=False, default="main")
    git_ref_type = Column(String(32), nullable=False, default="branch")  # branch, tag, commit
    git_branch = Column(String(128), nullable=False, default="main")
    git_subdir = Column(String(255), nullable=True)
    entrypoint = Column(String(255), nullable=True)

    # Git Credentials (Link Git Account or PAT)
    git_credential_type = Column(String(32), nullable=False, default="none")  # link_account, pat, none
    git_credential_nickname = Column(String(255), nullable=True)
    git_connection_id = Column(Integer, nullable=True)
    git_pat_enc = Column(Text, nullable=True)

    # Workspace Scoped Identity & Workload Execution Config
    workspace_identity = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    config = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_by_user_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
