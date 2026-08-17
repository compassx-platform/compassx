"""Asset Tag routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import AssetTagCreate, AssetTagResponse
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-tags", tags=["Asset Tags"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.get("", response_model=list[AssetTagResponse])
def list_asset_tags(asset_id: int | None = None, db: Session = Depends(get_asset_db)):
    return svc.list_asset_tags(db, asset_id=asset_id)


@router.post("", response_model=AssetTagResponse, status_code=201)
def create_asset_tag(body: AssetTagCreate, request: Request, db: Session = Depends(get_asset_db)):
    return svc.create_asset_tag(db, body, _current_user(request))


@router.delete("/{tag_id}", status_code=204)
def delete_asset_tag(tag_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_asset_tag(db, tag_id)
