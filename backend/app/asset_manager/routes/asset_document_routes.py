"""Asset Document routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.schemas.asset_manager import AssetDocumentCreate, AssetDocumentResponse
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-documents", tags=["Asset Documents"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.post("", response_model=AssetDocumentResponse, status_code=201)
def create_document(body: AssetDocumentCreate, request: Request, db: Session = Depends(get_asset_db)):
    return svc.create_document(db, body, _current_user(request))


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_asset_db)):
    svc.delete_document(db, doc_id)
