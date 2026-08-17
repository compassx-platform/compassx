"""Explorer query routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.explorer import ExplorerQuery, ExplorerResponse, ExplorerRow
from app.services.explorer_service import query_explorer
from app.services.enrichment_service import enrich_asset_names

router = APIRouter(prefix="/api/v1/explorer", tags=["Explorer"])


@router.post("/query", response_model=ExplorerResponse)
async def explorer_query(
    body: ExplorerQuery,
    authkey: str = Header(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = query_explorer(
        db,
        dataset_id=body.dataset,
        filters=body.filters,
        pagination=body.pagination,
        sort=body.sort if body.sort else None,
    )

    # Enrich asset names
    raw_items = result["items"]
    asset_ids = list({str(r.asset_id) for r in raw_items if r.asset_id})
    child_ids = list({str(r.child_asset_id) for r in raw_items if r.child_asset_id})
    all_ids = list(set(asset_ids + child_ids))

    names = await enrich_asset_names(all_ids, authkey) if all_ids else {}

    enriched = []
    for r in raw_items:
        enriched.append(ExplorerRow(
            id=r.id,
            record_id=r.record_id,
            asset_id=r.asset_id,
            asset_name=names.get(str(r.asset_id)),
            child_asset_id=r.child_asset_id,
            child_asset_name=names.get(str(r.child_asset_id)),
            breakdown_type=r.breakdown_type,
            severity=r.severity,
            description=r.description,
            timestamp=r.timestamp,
            status=r.status,
            created_by=r.created_by,
        ))

    return ExplorerResponse(
        items=enriched,
        total=result["total"],
        page=result["page"],
        size=result["size"],
        pages=result["pages"],
    )
