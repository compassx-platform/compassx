from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlActiveQuery, SqlQueryRecord


class QueryRecordStore:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **values) -> SqlQueryRecord:
        record = SqlQueryRecord(**values)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get(self, query_id: str) -> SqlQueryRecord | None:
        return self.db.get(SqlQueryRecord, query_id)

    def list(self, user_id: str | None = None, warehouse_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> list[SqlQueryRecord]:
        stmt = select(SqlQueryRecord)
        if user_id:
            stmt = stmt.where(SqlQueryRecord.user_id == user_id)
        if warehouse_id:
            stmt = stmt.where(SqlQueryRecord.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(SqlQueryRecord.status == status)
        stmt = stmt.order_by(SqlQueryRecord.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def set_status(self, query_id: str, status: str, **values) -> SqlQueryRecord | None:
        record = self.get(query_id)
        if not record:
            return None
        record.status = status
        for key, value in values.items():
            setattr(record, key, value)
        if status in {"succeeded", "failed", "cancelled"} and not record.completed_at:
            record.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

    def register_active(self, query_id: str, warehouse_id: str, engine_query_id: str | None) -> None:
        self.db.merge(SqlActiveQuery(query_id=query_id, warehouse_id=warehouse_id, engine_query_id=engine_query_id))
        self.db.commit()

    def get_active(self, query_id: str) -> SqlActiveQuery | None:
        return self.db.get(SqlActiveQuery, query_id)

    def deregister_active(self, query_id: str) -> None:
        active = self.get_active(query_id)
        if active:
            self.db.delete(active)
            self.db.commit()

    def count_active(self, warehouse_id: str) -> int:
        return int(self.db.scalar(select(func.count()).select_from(SqlActiveQuery).where(SqlActiveQuery.warehouse_id == warehouse_id)) or 0)

