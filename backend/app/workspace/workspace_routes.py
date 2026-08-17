"""Workspace-scoped APIs: /api/w/{slug}/api/...

- Workspace info + current user role
- Member management
- Catalog visibility (list objects, publish)
"""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.workspace.auth import get_current_principal
from app.workspace.middleware import WorkspaceContext
from app.workspace.models import (
    CatalogObject,
    CatalogPermission,
    Principal,
    Workspace,
    WorkspaceCatalog,
    WorkspaceMembership,
)
from app.workspace.schemas import (
    CatalogObjectOut,
    MemberAdd,
    MemberOut,
    MemberPatch,
    WorkspaceSlim,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/w/{slug}/api", tags=["workspace"])


def _get_workspace_ctx(request: Request) -> WorkspaceContext:
    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        raise HTTPException(status_code=400, detail="Missing workspace context")
    return ctx


def _require_workspace_admin(ctx: WorkspaceContext) -> None:
    if ctx.principal_role not in ("admin",) and not ctx.is_account_admin:
        raise HTTPException(status_code=403, detail="Workspace admin required")


# ── Workspace info ────────────────────────────────────────────────────────────

@router.get("/workspace")
def get_workspace_info(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    return {
        "id": ws.id,
        "name": ws.name,
        "slug": ws.slug,
        "status": ws.status,
        "url": f"/w/{ws.slug}",
        "current_user_role": ctx.principal_role,
        "is_account_admin": ctx.is_account_admin,
    }


# ── Members ───────────────────────────────────────────────────────────────────

@router.get("/workspace/members", response_model=list[MemberOut])
def list_members(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.workspace_id == ctx.workspace_id)
        .all()
    )
    result = []
    for m in memberships:
        principal = db.query(Principal).filter(Principal.id == m.principal_id).first()
        result.append(MemberOut(
            id=m.id,
            workspace_id=m.workspace_id,
            principal_id=m.principal_id,
            role=m.role,
            granted_at=m.granted_at,
            principal=principal,
        ))
    return result


@router.post("/workspace/members", response_model=MemberOut, status_code=201)
def add_member(
    slug: str,
    body: MemberAdd,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == ctx.workspace_id,
        WorkspaceMembership.principal_id == body.principal_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Principal already a member")

    principal = db.query(Principal).filter(Principal.id == body.principal_id).first()
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found")

    m = WorkspaceMembership(
        id=str(uuid4()),
        workspace_id=ctx.workspace_id,
        principal_id=body.principal_id,
        role=body.role,
        granted_by=ctx.principal_id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return MemberOut(
        id=m.id,
        workspace_id=m.workspace_id,
        principal_id=m.principal_id,
        role=m.role,
        granted_at=m.granted_at,
        principal=principal,
    )


@router.patch("/workspace/members/{member_id}", response_model=MemberOut)
def update_member_role(
    slug: str,
    member_id: str,
    body: MemberPatch,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.id == member_id,
        WorkspaceMembership.workspace_id == ctx.workspace_id,
    ).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    m.role = body.role
    db.commit()
    db.refresh(m)
    principal = db.query(Principal).filter(Principal.id == m.principal_id).first()
    return MemberOut(
        id=m.id,
        workspace_id=m.workspace_id,
        principal_id=m.principal_id,
        role=m.role,
        granted_at=m.granted_at,
        principal=principal,
    )


@router.delete("/workspace/members/{member_id}", status_code=204)
def remove_member(
    slug: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.id == member_id,
        WorkspaceMembership.workspace_id == ctx.workspace_id,
    ).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(m)
    db.commit()


# ── Catalog visibility ────────────────────────────────────────────────────────

@router.get("/catalog", response_model=list[dict])
def list_catalogs(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    catalogs = db.query(WorkspaceCatalog).filter(
        WorkspaceCatalog.account_id == ws.account_id
    ).all()
    return [
        {"id": c.id, "name": c.name, "type": c.type, "is_system": c.is_system}
        for c in catalogs
    ]


@router.get("/catalog/{catalog_name}/schemas")
def list_schemas(
    slug: str,
    catalog_name: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    catalog = db.query(WorkspaceCatalog).filter(
        WorkspaceCatalog.account_id == ws.account_id,
        WorkspaceCatalog.name == catalog_name,
    ).first()
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return [{"id": s.id, "name": s.name} for s in catalog.schemas]


@router.get("/catalog/{catalog_name}/{schema_name}/objects", response_model=list[CatalogObjectOut])
def list_objects(
    slug: str,
    catalog_name: str,
    schema_name: str,
    request: Request,
    object_type: str | None = None,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    catalog = db.query(WorkspaceCatalog).filter(
        WorkspaceCatalog.account_id == ws.account_id,
        WorkspaceCatalog.name == catalog_name,
    ).first()
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")

    from app.workspace.models import WorkspaceCatalogSchema
    schema = db.query(WorkspaceCatalogSchema).filter(
        WorkspaceCatalogSchema.catalog_id == catalog.id,
        WorkspaceCatalogSchema.name == schema_name,
    ).first()
    if schema is None:
        raise HTTPException(status_code=404, detail="Schema not found")

    q = db.query(CatalogObject).filter(
        CatalogObject.schema_id == schema.id,
        (CatalogObject.visibility == "global") |
        (CatalogObject.home_workspace_id == ctx.workspace_id),
    )
    if object_type:
        q = q.filter(CatalogObject.object_type == object_type)
    return q.all()


@router.post("/catalog/objects/{object_id}/publish", status_code=200)
def publish_object(
    slug: str,
    object_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    obj = db.query(CatalogObject).filter(CatalogObject.id == object_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    if obj.home_workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=403, detail="Object belongs to a different workspace")
    if obj.visibility == "global":
        raise HTTPException(status_code=400, detail="Object already published")

    # Check PUBLISH privilege
    perm = db.query(CatalogPermission).filter(
        CatalogPermission.securable_type == "object",
        CatalogPermission.securable_id == object_id,
        CatalogPermission.principal_id == ctx.principal_id,
        CatalogPermission.privilege == "PUBLISH",
    ).first()
    # Schema MANAGE also grants publish
    schema_manage = db.query(CatalogPermission).filter(
        CatalogPermission.securable_type == "schema",
        CatalogPermission.securable_id == obj.schema_id,
        CatalogPermission.principal_id == ctx.principal_id,
        CatalogPermission.privilege == "MANAGE",
    ).first()

    if perm is None and schema_manage is None and not ctx.is_account_admin:
        raise HTTPException(status_code=403, detail="PUBLISH privilege required")

    obj.visibility = "global"
    obj.home_workspace_id = None
    db.commit()
    return {"status": "published", "object_id": object_id}
