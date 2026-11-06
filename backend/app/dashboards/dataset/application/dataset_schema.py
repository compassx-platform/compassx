from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.dashboards.shared.support import _authorized_dataset, _run_dashboard_sql


class DatasetSchema:
    async def execute(self, dataset_id: str, request: Request, db: Session, system_db: Session, guard: Guard):
        """Return column schema for a dataset by running a zero-row warehouse query."""
        dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

        if dataset.get("schema"):
            return dataset["schema"]

        sql = dataset.get("sql", "").strip()
        if not sql:
            return []

        limit_sql = f"SELECT * FROM ({sql}) _q LIMIT 0"
        try:
            result = await _run_dashboard_sql(
                request, system_db, limit_sql, max_rows=1,
                warehouse_id=(dataset.get("warehouse_id") if isinstance(dataset, dict) else None),
                dashboard_id=dashboard_id, dataset_id=dataset_id
            )
            return [{"name": col, "type": "unknown"} for col in result["columns"]]
        except HTTPException:
            return []
        except Exception:
            return []


def dataset_schema(dataset_id, request, db, system_db, guard):
    return DatasetSchema().execute(dataset_id, request, db, system_db, guard)
