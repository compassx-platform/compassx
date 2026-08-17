"""Asset Event routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import (
    AssetEventCreate,
    AssetEventResponse,
    AssetEventUpdate,
)
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-events", tags=["Asset Events"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.get("", response_model=list[AssetEventResponse])
def list_events(
    asset_id: int | None = Query(None),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    started_after: str | None = Query(None),
    started_before: str | None = Query(None),
    db: Session = Depends(get_asset_db),
):
    return svc.list_events(db, asset_id, event_type, severity, started_after, started_before)


@router.post("", response_model=AssetEventResponse, status_code=201)
def create_event(body: AssetEventCreate, request: Request, db: Session = Depends(get_asset_db)):
    return svc.create_event(db, body, _current_user(request))


@router.get("/{event_id}", response_model=AssetEventResponse)
def get_event(event_id: int, db: Session = Depends(get_asset_db)):
    return svc.get_event(db, event_id)


@router.put("/{event_id}", response_model=AssetEventResponse)
def update_event(event_id: int, body: AssetEventUpdate, db: Session = Depends(get_asset_db)):
    return svc.update_event(db, event_id, body)


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_event(db, event_id)
