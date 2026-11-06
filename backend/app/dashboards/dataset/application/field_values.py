import re

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.dashboards.shared.support import _authorized_dataset, _run_dashboard_sql


class FieldValues:
    async def execute(
        self,
        dataset_id: str,
        request: Request,
        field: str,
        db: Session,
        system_db: Session,
        guard: Guard,
    ):
        """Return distinct values for a field in the dataset."""
        dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

        sql = dataset.get("sql", "").strip()
        if not sql:
            return []

        # ``field`` is interpolated into the query as an identifier, so it is
        # restricted to identifier characters. Stripping double quotes was not
        # enough: a backslash or a comment sequence still escaped the position.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", field):
            raise HTTPException(status_code=400, detail="Invalid field name")
        distinct_sql = f'SELECT DISTINCT "{field}" FROM ({sql}) _q WHERE "{field}" IS NOT NULL ORDER BY 1 LIMIT 1000'
        try:
            result = await _run_dashboard_sql(
                request,
                system_db,
                distinct_sql,
                max_rows=1000,
                warehouse_id=dataset.get("warehouse_id"),
                dashboard_id=dashboard_id,
                dataset_id=dataset_id,
            )
            if not result["columns"]:
                return []
            col = result["columns"][0]
            return [str(row.get(col, "")) if isinstance(row, dict) else str(row[0] if row else "") for row in result["rows"]]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Query error: {exc}")


def field_values(dataset_id, request, field, db, system_db, guard):
    return FieldValues().execute(dataset_id, request, field, db, system_db, guard)
