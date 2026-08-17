"""Explorer service – queries projection table via Dataset DSL (UDAL)."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from app.models.projection import BreakdownEventFlat
from app.models.dataset import Dataset


def query_explorer(
    db: Session,
    dataset_id: str,
    filters: dict[str, Any],
    pagination: dict[str, int],
    sort: dict[str, str] | None = None,
) -> dict:
    """Execute an explorer query via the Dataset Layer.

    1. Look up dataset in registry
    2. Build query against projection table
    3. Apply filters, pagination, sorting
    4. Return results
    """
    # Step 1: Resolve dataset
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        return {"items": [], "total": 0, "page": 1, "size": 50, "pages": 0}

    # Step 2: Build base query (for now, only breakdown_events_flat)
    query = db.query(BreakdownEventFlat).filter(BreakdownEventFlat.status != "DELETED")

    # Step 3: Apply filters
    if "asset_id" in filters:
        query = query.filter(BreakdownEventFlat.asset_id == str(filters["asset_id"]))

    if "severity" in filters:
        query = query.filter(BreakdownEventFlat.severity == filters["severity"])

    if "status" in filters:
        query = query.filter(BreakdownEventFlat.status == filters["status"])

    if "breakdown_type" in filters:
        query = query.filter(BreakdownEventFlat.breakdown_type == filters["breakdown_type"])

    if "time_range" in filters:
        tr = filters["time_range"]
        if isinstance(tr, list) and len(tr) == 2:
            query = query.filter(BreakdownEventFlat.timestamp >= tr[0])
            query = query.filter(BreakdownEventFlat.timestamp <= tr[1])

    if "search" in filters and filters["search"]:
        search_term = f"%{filters['search']}%"
        query = query.filter(
            BreakdownEventFlat.description.ilike(search_term)
            | BreakdownEventFlat.breakdown_type.ilike(search_term)
        )

    # Step 4: Sorting
    if sort:
        for field, direction in sort.items():
            col = getattr(BreakdownEventFlat, field, None)
            if col is not None:
                query = query.order_by(desc(col) if direction == "desc" else asc(col))
    else:
        query = query.order_by(desc(BreakdownEventFlat.timestamp))

    # Step 5: Count + paginate
    total = query.count()
    page = pagination.get("page", 1)
    size = pagination.get("size", 50)
    pages = math.ceil(total / size) if size > 0 else 0

    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }
