import csv
import io

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.dashboards.shared.support import _authorized_dataset, _run_dashboard_sql


class ExportDataset:
    async def execute(
        self,
        dataset_id: str,
        request: Request,
        format: str,
        db: Session,
        system_db: Session,
        guard: Guard,
    ):
        """Download dataset result as CSV/TSV/Excel using the warehouse engine."""
        dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

        sql = dataset.get("sql", "").strip()
        if not sql:
            raise HTTPException(status_code=400, detail="Dataset has no SQL defined")

        try:
            result = await _run_dashboard_sql(
                request,
                system_db,
                sql,
                max_rows=100_000,
                warehouse_id=dataset.get("warehouse_id"),
                dashboard_id=dashboard_id,
                dataset_id=dataset_id,
            )
            columns = result["columns"]
            rows = [
                [row.get(col) if isinstance(row, dict) else (row[idx] if idx < len(row) else None) for idx, col in enumerate(columns)]
                for row in result["rows"]
            ]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Query error: {exc}")

        if format == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.append(columns)
                for row in rows[:100_000]:
                    ws.append(row)
                buf = io.BytesIO()
                wb.save(buf)
                buf.seek(0)
                return StreamingResponse(
                    buf,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=dataset.xlsx"},
                )
            except ImportError:
                raise HTTPException(status_code=500, detail="openpyxl not installed")

        delimiter = "\t" if format == "tsv" else ","
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=delimiter)
        writer.writerow(columns)
        writer.writerows(rows)
        buf.seek(0)
        ext = "tsv" if format == "tsv" else "csv"
        return StreamingResponse(
            iter([buf.read()]),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=dataset.{ext}"},
        )


def export_dataset(dataset_id, request, format, db, system_db, guard):
    return ExportDataset().execute(dataset_id, request, format, db, system_db, guard)
