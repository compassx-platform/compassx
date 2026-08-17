"""Asset Type CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import (
    AssetTypeCreate,
    AssetTypeListResponse,
    AssetTypeResponse,
    AssetTypeUpdate,
    AssetTypeTagCreate,
    AssetTypeTagResponse,
    AssetTypeTagUpdate,
    MetadataSchema,
)
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-types", tags=["Asset Types"])


@router.get("", response_model=list[AssetTypeListResponse])
def list_asset_types(
    industry_tag: str | None = Query(None),
    category: str | None = Query(None),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_asset_db),
):
    return svc.list_asset_types(db, industry_tag, category, include_deleted)


@router.post("", response_model=AssetTypeResponse, status_code=201)
def create_asset_type(body: AssetTypeCreate, db: Session = Depends(get_asset_db)):
    return svc.create_asset_type(db, body)


@router.get("/{type_id}", response_model=AssetTypeResponse)
def get_asset_type(type_id: int, db: Session = Depends(get_asset_db)):
    return svc.get_asset_type(db, type_id)


@router.put("/{type_id}", response_model=AssetTypeResponse)
def update_asset_type(type_id: int, body: AssetTypeUpdate, db: Session = Depends(get_asset_db)):
    return svc.update_asset_type(db, type_id, body)


@router.delete("/deleted/permanent")
def purge_deleted_asset_types(db: Session = Depends(get_asset_db)):
    return {"deleted": svc.purge_deleted_asset_types(db)}


@router.delete("/{type_id}", status_code=204)
def delete_asset_type(type_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_asset_type(db, type_id)


@router.delete("/{type_id}/permanent", status_code=204)
def purge_asset_type(type_id: int, db: Session = Depends(get_asset_db)):
    svc.purge_asset_type(db, type_id)


@router.get("/{type_id}/schema", response_model=MetadataSchema)
def get_asset_type_schema(type_id: int, db: Session = Depends(get_asset_db)):
    obj = svc.get_asset_type(db, type_id)
    return obj.metadata_schema


@router.put("/{type_id}/schema", response_model=AssetTypeResponse)
def update_asset_type_schema(type_id: int, schema: MetadataSchema, db: Session = Depends(get_asset_db)):
    return svc.update_asset_type_schema(db, type_id, schema)


@router.get("/{type_id}/tags", response_model=list[AssetTypeTagResponse])
def list_asset_type_tags(type_id: int, db: Session = Depends(get_asset_db)):
    return svc.list_asset_type_tags(db, type_id)


@router.post("/{type_id}/tags", response_model=AssetTypeTagResponse, status_code=201)
def create_asset_type_tag(type_id: int, body: AssetTypeTagCreate, db: Session = Depends(get_asset_db)):
    return svc.create_asset_type_tag(db, type_id, body)


@router.put("/{type_id}/tags/{tag_def_id}", response_model=AssetTypeTagResponse)
def update_asset_type_tag(
    type_id: int, tag_def_id: int, body: AssetTypeTagUpdate, db: Session = Depends(get_asset_db)
):
    return svc.update_asset_type_tag(db, type_id, tag_def_id, body)


@router.delete("/{type_id}/tags/{tag_def_id}", status_code=204)
def delete_asset_type_tag(type_id: int, tag_def_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_asset_type_tag(db, type_id, tag_def_id)
