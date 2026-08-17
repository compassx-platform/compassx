"""Pydantic schemas for workspace/account/auth APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


# ── Auth ────────────────────────────────────────────────────────────────────


class PrincipalOut(BaseModel):
    id: str
    account_id: str
    type: str
    email: str | None
    name: str
    is_account_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceSlim(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    url: str
    role: str | None = None

    class Config:
        from_attributes = True


# ── Account ─────────────────────────────────────────────────────────────────

class AccountOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountPatch(BaseModel):
    name: str


# ── Workspace ───────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str
    slug: str
    storage_backend: str
    storage_config: dict[str, Any]


class WorkspacePatch(BaseModel):
    name: str | None = None
    storage_config: dict[str, Any] | None = None


class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    storage_backend: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Principal CRUD ───────────────────────────────────────────────────────────

class PrincipalCreate(BaseModel):
    type: str = "user"
    email: str | None = None
    name: str
    password: str | None = None
    is_account_admin: bool = False


class PrincipalPatch(BaseModel):
    name: str | None = None
    is_account_admin: bool | None = None
    is_active: bool | None = None


class PasswordResetRequest(BaseModel):
    new_password: str


# ── Workspace membership ─────────────────────────────────────────────────────

class MemberAdd(BaseModel):
    principal_id: str
    role: str = "member"


class MemberPatch(BaseModel):
    role: str


class MemberOut(BaseModel):
    id: str
    workspace_id: str
    principal_id: str
    role: str
    granted_at: datetime
    principal: PrincipalOut | None = None

    class Config:
        from_attributes = True


# ── Catalog visibility ───────────────────────────────────────────────────────

class CatalogObjectOut(BaseModel):
    id: str
    schema_id: str
    name: str
    object_type: str
    visibility: str
    home_workspace_id: str | None
    blob_path: str | None
    owner_principal_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True
