from typing import Any, Dict

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.dashboards.shared.support import (
    _authorized_dataset,
    _bind_params,
    _run_dashboard_sql,
    _securable,
)


class QueryDataset:
    async def execute(
        self,
        dataset_id: str,
        request: Request,
        body: Dict[str, Any] | None,
        db: Session,
        system_db: Session,
        guard: Guard,
    ):
        """Run dataset SQL through the SQL warehouse engine and return rows."""
        payload = body or {}

        dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

        # The dataset editor previews SQL before it is saved, so an override is
        # accepted — but only from someone who could have saved it and run it
        # anyway. Without this check, a viewer could pass any SQL they liked and
        # the dataset id was decoration on an open query runner.
        override = (payload.get("sql") or "").strip()
        if override:
            guard.require(Privilege.EDIT, _securable(db, dashboard_id))
            sql = override
        else:
            sql = (dataset.get("sql") or "").strip()
        if not sql:
            raise HTTPException(status_code=400, detail="Dataset has no SQL defined")

        sql = _bind_params(sql, payload.get("params", {}))

        warehouse_id = payload.get("warehouse_id")
        try:
            result = await _run_dashboard_sql(request, system_db, sql, warehouse_id=warehouse_id, dashboard_id=dashboard_id, dataset_id=dataset_id)
            return {
                "columns": result["columns"],
                "rows": result["rows"],
                "rowCount": result.get("row_count", result.get("rows_returned", len(result["rows"]))),
                "executionMs": result.get("execution_time_ms", result.get("duration_ms", 0)),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Query error: {exc}")


def query_dataset(dataset_id, request, body, db, system_db, guard):
    return QueryDataset().execute(dataset_id, request, body, db, system_db, guard)
