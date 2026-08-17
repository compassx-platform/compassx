from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlWarehouse

VALID_ENGINES = {"clickhouse", "duckdb", "postgres"}
VALID_STATUSES = {"running", "stopped", "starting", "stopping", "error"}


def list_warehouses(db: Session, workspace_id: str | None = None) -> list[SqlWarehouse]:
    stmt = select(SqlWarehouse)
    if workspace_id:
        stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
    else:
        stmt = stmt.filter(SqlWarehouse.workspace_id == None)
    return list(db.scalars(stmt.order_by(SqlWarehouse.created_at.desc())))


def get_warehouse_by_id(db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse | None:
    stmt = select(SqlWarehouse).filter(SqlWarehouse.id == warehouse_id)
    if workspace_id:
        stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
    else:
        stmt = stmt.filter(SqlWarehouse.workspace_id == None)
    return db.scalars(stmt).first()


def create_warehouse(db: Session, req, created_by: str, workspace_id: str | None = None) -> SqlWarehouse:
    if req.engine not in VALID_ENGINES:
        raise HTTPException(400, f"Unsupported engine '{req.engine}'.")
    warehouse = SqlWarehouse(
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        engine=req.engine,
        config=req.config,
        resource_policy=req.resource_policy,
        created_by=created_by,
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse_status(db: Session, warehouse_id: str, status: str, workspace_id: str | None = None) -> SqlWarehouse:
    if status not in VALID_STATUSES:
        raise HTTPException(400, f"Unsupported warehouse status '{status}'.")
    warehouse = get_warehouse_by_id(db, warehouse_id, workspace_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    warehouse.status = status
    warehouse.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, warehouse_id: str, workspace_id: str | None = None) -> None:
    warehouse = get_warehouse_by_id(db, warehouse_id, workspace_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    db.delete(warehouse)
    db.commit()

