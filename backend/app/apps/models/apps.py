"""CompassX Apps — SQLAlchemy ORM models.

All 6 tables from spec §3, using AccountBase (compassx_account control-plane DB)
alongside catalog and workspace tables.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    Integer, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# App registration (catalog asset)
# ---------------------------------------------------------------------------

class App(Base):
    """Top-level app record — the catalog asset entry for a CompassX App."""

    __tablename__ = "apps"

    app_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalog_fqn = Column(Text, nullable=False)          # catalog.schema.app_name
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    terminal_enabled_prod = Column(Boolean, nullable=False, default=False)
    max_concurrent_branches = Column(Integer, nullable=False, default=5)
    # 'git' | 'native'
    versioning_backend = Column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("versioning_backend IN ('git', 'native')", name="ck_apps_versioning_backend"),
    )

    branches = relationship("AppBranch", back_populates="app", cascade="all, delete-orphan")
    pods = relationship("AppPod", back_populates="app", cascade="all, delete-orphan")
    production_pointer = relationship("AppProductionPointer", back_populates="app", uselist=False, cascade="all, delete-orphan")
    credential_grant = relationship("AppCredentialGrant", back_populates="app", uselist=False, cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Git config resolution: workspace-level checked first, else platform-level
# ---------------------------------------------------------------------------

class GitConfig(Base):
    """Git provider configuration scoped to a platform or specific workspace."""

    __tablename__ = "git_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(Text, nullable=False)            # 'platform' | 'workspace'
    workspace_id = Column(UUID(as_uuid=True), nullable=True)  # null when scope='platform'
    provider = Column(Text, nullable=False)         # github | gitlab | gitea | generic
    server_url = Column(Text, nullable=False)
    auth_ref = Column(Text, nullable=False)         # secret reference, never raw credential

    __table_args__ = (
        CheckConstraint("scope IN ('platform', 'workspace')", name="ck_git_config_scope"),
        UniqueConstraint("scope", "workspace_id", name="uq_git_config_scope_workspace"),
    )


# ---------------------------------------------------------------------------
# Native backend: immutable commit chain
# ---------------------------------------------------------------------------

class AppCommit(Base):
    """Immutable commit record for the native content-addressable backend.

    For the git backend, commit_id mirrors the git commit SHA stored as text
    and this row is also inserted to give CompassX-side bookkeeping a uniform
    model across both backends.
    """

    __tablename__ = "app_commits"

    commit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.app_id", ondelete="CASCADE"), nullable=False)
    parent_commit_id = Column(UUID(as_uuid=True), ForeignKey("app_commits.commit_id"), nullable=True)
    author = Column(Text, nullable=False)               # user_id or 'pi-agent'
    message = Column(Text, nullable=True)
    tree_manifest_hash = Column(Text, nullable=False)   # content hash of {path: content_hash} JSON
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    parent = relationship("AppCommit", remote_side="AppCommit.commit_id", uselist=False)


# ---------------------------------------------------------------------------
# Branch pointer
# ---------------------------------------------------------------------------

class AppBranch(Base):
    """Branch pointer — used by both git and native backends.

    For the git backend, `name` maps 1:1 to a real git branch and
    `head_commit_id` mirrors the git HEAD SHA.
    """

    __tablename__ = "app_branches"

    branch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.app_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    head_commit_id = Column(UUID(as_uuid=True), ForeignKey("app_commits.commit_id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "name", name="uq_app_branches_app_name"),
    )

    app = relationship("App", back_populates="branches")
    head_commit = relationship("AppCommit", foreign_keys=[head_commit_id])
    pods = relationship("AppPod", back_populates="branch")


# ---------------------------------------------------------------------------
# Production pointer: decoupled from any specific branch
# ---------------------------------------------------------------------------

class AppProductionPointer(Base):
    """Points to the currently live commit on the production pod.

    Decoupled from branches — publish is always a pointer switch, never a merge.
    """

    __tablename__ = "app_production_pointer"

    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.app_id", ondelete="CASCADE"), primary_key=True)
    current_commit_id = Column(UUID(as_uuid=True), ForeignKey("app_commits.commit_id"), nullable=True)
    source_branch_id = Column(UUID(as_uuid=True), ForeignKey("app_branches.branch_id"), nullable=True)
    switched_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    switched_by = Column(UUID(as_uuid=True), nullable=False)

    app = relationship("App", back_populates="production_pointer")
    current_commit = relationship("AppCommit", foreign_keys=[current_commit_id])
    source_branch = relationship("AppBranch", foreign_keys=[source_branch_id])


# ---------------------------------------------------------------------------
# Running pod registry (branch-preview and production pods)
# ---------------------------------------------------------------------------

class AppPod(Base):
    """Registry of all running pods for an app (branch previews + production)."""

    __tablename__ = "app_pods"

    pod_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.app_id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("app_branches.branch_id"), nullable=True)  # null for production
    pod_kind = Column(Text, nullable=False)             # 'branch' | 'production'
    k8s_pod_name = Column(Text, nullable=False)
    preview_url = Column(Text, nullable=False)
    terminal_enabled = Column(Boolean, nullable=False)
    status = Column(Text, nullable=False, default="starting")  # starting|running|failed|terminated
    commit_id = Column(UUID(as_uuid=True), ForeignKey("app_commits.commit_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint("pod_kind IN ('branch', 'production')", name="ck_app_pods_pod_kind"),
        CheckConstraint("status IN ('starting', 'running', 'failed', 'terminated')", name="ck_app_pods_status"),
    )

    app = relationship("App", back_populates="pods")
    branch = relationship("AppBranch", back_populates="pods")
    commit = relationship("AppCommit", foreign_keys=[commit_id])


# ---------------------------------------------------------------------------
# Per-app credential grant (scope: per-app, not per-branch/per-pod)
# ---------------------------------------------------------------------------

class AppCredentialGrant(Base):
    """Catalog and volume access grants for an app.

    Every pod for the app (branch or production) mints a short-lived scoped
    token against this same grant at pod startup.
    """

    __tablename__ = "app_credential_grants"

    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.app_id", ondelete="CASCADE"), primary_key=True)
    # list of {catalog, schema, table|*, privilege}
    catalog_grants = Column(JSONB, nullable=False)
    volume_grants = Column(JSONB, nullable=False, default=list)

    app = relationship("App", back_populates="credential_grant")
