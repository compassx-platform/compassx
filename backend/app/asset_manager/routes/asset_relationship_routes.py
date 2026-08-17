"""Asset Relationship routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import AssetRelationshipCreate, AssetRelationshipResponse
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-relationships", tags=["Asset Relationships"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.get("", response_model=list[AssetRelationshipResponse])
def list_relationships(
    from_asset_id: int | None = Query(None),
    to_asset_id: int | None = Query(None),
    type: str | None = Query(None),
    db: Session = Depends(get_asset_db),
):
    return svc.list_relationships(db, from_asset_id, to_asset_id, type)


@router.post("", response_model=AssetRelationshipResponse, status_code=201)
def create_relationship(body: AssetRelationshipCreate, request: Request, db: Session = Depends(get_asset_db)):
    return svc.create_relationship(db, body, _current_user(request))


@router.delete("/{rel_id}", status_code=204)
def delete_relationship(rel_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_relationship(db, rel_id)
