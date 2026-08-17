"""Asset Instance CRUD and hierarchy routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import (
    AssetDocumentCreate,
    AssetDocumentResponse,
    AssetEventResponse,
    AssetInstanceCreate,
    AssetInstanceListResponse,
    AssetInstanceResponse,
    AssetInstanceUpdate,
    AssetParentUpdate,
    AssetRelationshipResponse,
    AssetStatusUpdate,
    AssetTagResponse,
    AssetVersionResponse,
    HierarchyNode,
    PaginatedAssets,
)
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-instances", tags=["Asset Instances"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def _enrich(instance: Any, db: Session) -> AssetInstanceResponse:
    resp = AssetInstanceResponse.model_validate(instance)
    if instance.asset_type:
        resp.asset_type_name = instance.asset_type.name
        resp.asset_type_slug = instance.asset_type.slug
    return resp


def _enrich_list(instance: Any, db: Session) -> AssetInstanceListResponse:
    resp = AssetInstanceListResponse.model_validate(instance)
    if instance.asset_type:
        resp.asset_type_name = instance.asset_type.name
        resp.asset_type_slug = instance.asset_type.slug
    return resp


@router.get("", response_model=PaginatedAssets)
def list_instances(
    q: str | None = Query(None),
    type_id: int | None = Query(None),
    status: list[str] | None = Query(None),
    parent_id: int | None = Query(None),
    path_prefix: str | None = Query(None),
    industry: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    sort: str = Query("-updated_at"),
    db: Session = Depends(get_asset_db),
):
    result = svc.list_instances(db, q, type_id, status, parent_id, path_prefix, industry, cursor, limit, sort)
    result["data"] = [_enrich_list(item, db) for item in result["data"]]
    return result


@router.get("/by-path/{path:path}", response_model=AssetInstanceResponse)
def get_instance_by_path(path: str, db: Session = Depends(get_asset_db)):
    obj = svc.get_instance_by_path(db, path)
    return _enrich(obj, db)


@router.post("", response_model=AssetInstanceResponse, status_code=201)
def create_instance(body: AssetInstanceCreate, request: Request, db: Session = Depends(get_asset_db)):
    obj = svc.create_instance(db, body, _current_user(request))
    return _enrich(obj, db)


@router.get("/{instance_id}", response_model=AssetInstanceResponse)
def get_instance(instance_id: int, db: Session = Depends(get_asset_db)):
    obj = svc.get_instance(db, instance_id)
    return _enrich(obj, db)


@router.put("/{instance_id}", response_model=AssetInstanceResponse)
def update_instance(instance_id: int, body: AssetInstanceUpdate, request: Request, db: Session = Depends(get_asset_db)):
    obj = svc.update_instance(db, instance_id, body, _current_user(request))
    return _enrich(obj, db)


@router.patch("/{instance_id}/status", response_model=AssetInstanceResponse)
def update_status(instance_id: int, body: AssetStatusUpdate, request: Request, db: Session = Depends(get_asset_db)):
    obj = svc.update_instance_status(db, instance_id, body, _current_user(request))
    return _enrich(obj, db)


@router.patch("/{instance_id}/parent", response_model=AssetInstanceResponse)
def reparent(instance_id: int, body: AssetParentUpdate, request: Request, db: Session = Depends(get_asset_db)):
    obj = svc.reparent_instance(db, instance_id, body, _current_user(request))
    return _enrich(obj, db)


@router.delete("/deleted/permanent")
def purge_deleted_instances(db: Session = Depends(get_asset_db)):
    return {"deleted": svc.purge_deleted_instances(db)}


@router.delete("/{instance_id}", status_code=204)
def delete_instance(instance_id: int, request: Request, db: Session = Depends(get_asset_db)):
    svc.soft_delete_instance(db, instance_id, _current_user(request))


@router.get("/{instance_id}/children", response_model=list[AssetInstanceListResponse])
def get_children(
    instance_id: int,
    include_deleted: bool = Query(False),
    db: Session = Depends(get_asset_db),
):
    items = svc.get_children(db, instance_id, include_deleted=include_deleted)
    return [_enrich_list(i, db) for i in items]


@router.get("/{instance_id}/subtree", response_model=list[AssetInstanceListResponse])
def get_subtree(instance_id: int, db: Session = Depends(get_asset_db)):
    items = svc.get_subtree(db, instance_id)
    return [_enrich_list(i, db) for i in items]


@router.get("/{instance_id}/ancestors", response_model=list[AssetInstanceListResponse])
def get_ancestors(instance_id: int, db: Session = Depends(get_asset_db)):
    items = svc.get_ancestors(db, instance_id)
    return [_enrich_list(i, db) for i in items]


@router.get("/{instance_id}/versions", response_model=list[AssetVersionResponse])
def get_versions(instance_id: int, db: Session = Depends(get_asset_db)):
    return svc.get_versions(db, instance_id)


@router.get("/{instance_id}/versions/{version}", response_model=AssetVersionResponse)
def get_version(instance_id: int, version: int, db: Session = Depends(get_asset_db)):
    return svc.get_version(db, instance_id, version)


@router.get("/{instance_id}/events", response_model=list[AssetEventResponse])
def get_instance_events(instance_id: int, db: Session = Depends(get_asset_db)):
    return svc.list_events(db, asset_id=instance_id, event_type=None, severity=None, started_after=None, started_before=None)


@router.get("/{instance_id}/tags", response_model=list[AssetTagResponse])
def get_instance_tags(instance_id: int, db: Session = Depends(get_asset_db)):
    obj = svc.get_instance(db, instance_id)
    return obj.tags


@router.get("/{instance_id}/documents", response_model=list[AssetDocumentResponse])
def get_instance_documents(instance_id: int, db: Session = Depends(get_asset_db)):
    obj = svc.get_instance(db, instance_id)
    return obj.documents


@router.get("/{instance_id}/relationships", response_model=list[AssetRelationshipResponse])
def get_instance_relationships(instance_id: int, db: Session = Depends(get_asset_db)):
    from app.asset_manager.models.asset_manager import AssetRelationship
    from sqlalchemy import or_
    return db.query(AssetRelationship).filter(
        or_(
            AssetRelationship.from_asset_id == instance_id,
            AssetRelationship.to_asset_id == instance_id,
        )
    ).all()


@router.post("/{instance_id}/documents", response_model=AssetDocumentResponse, status_code=201)
def add_document(instance_id: int, body: AssetDocumentCreate, request: Request, db: Session = Depends(get_asset_db)):
    body.asset_id = instance_id
    return svc.create_document(db, body, _current_user(request))
