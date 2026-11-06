from __future__ import annotations

import json
import time
from typing import Any

import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session

from app.models.data_catalog import CatalogConnection
from app.schemas.data_catalog import (
    ColumnInfo,
    ConnectionCreate,
    ConnectionUpdate,
    SqlExecuteResponse,
    TablePreviewResponse,
)

def update_connection(db: Session, conn_id: int, data: ConnectionUpdate) -> CatalogConnection | None:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        return None
    if data.name is not None:
        record.name = data.name
    if data.host is not None:
        record.host = data.host
    if data.port is not None:
        record.port = data.port
    if data.username is not None:
        record.username = data.username
    if data.password is not None:
        record.password_enc = svc.encrypt_password(data.password)
    if data.default_database is not None:
        record.default_database = data.default_database
    db.commit()
    db.refresh(record)
    return record
