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


def get_default_warehouse(db: Session, workspace_id: str | None = None) -> SqlWarehouse | None:
    stmt = select(SqlWarehouse)
    if workspace_id:
        stmt = stmt.filter(SqlWarehouse.workspace_id == workspace_id)
    else:
        stmt = stmt.filter(SqlWarehouse.workspace_id == None)
    
    # 1. Prefer warehouse explicitly marked as is_default
    wh = db.scalars(stmt.filter(SqlWarehouse.is_default == True)).first()
    if wh:
        return wh

    # 2. Fall back to name == "default"
    wh = db.scalars(stmt.filter(SqlWarehouse.name == "default")).first()
    if wh:
        return wh

    # 3. Fall back to first created
    return db.scalars(stmt.order_by(SqlWarehouse.created_at.asc())).first()


def set_default_warehouse(db: Session, warehouse_id: str, workspace_id: str | None = None) -> SqlWarehouse:
    target = get_warehouse_by_id(db, warehouse_id, workspace_id)
    if not target:
        raise HTTPException(404, "Warehouse not found")

    # Unset is_default on other warehouses in this workspace
    all_whs = list_warehouses(db, workspace_id)
    for wh in all_whs:
        if wh.id != target.id and wh.is_default:
            wh.is_default = False

    target.is_default = True
    target.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(target)
    return target


def create_warehouse(db: Session, req, created_by: str, workspace_id: str | None = None) -> SqlWarehouse:
    if req.engine not in VALID_ENGINES:
        raise HTTPException(400, f"Unsupported engine '{req.engine}'.")

    # If this is the first warehouse in the workspace, or explicitly requested as default
    existing = list_warehouses(db, workspace_id)
    should_be_default = getattr(req, "is_default", False) or len(existing) == 0

    if should_be_default:
        for wh in existing:
            if wh.is_default:
                wh.is_default = False

    warehouse = SqlWarehouse(
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        engine=req.engine,
        is_default=should_be_default,
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

