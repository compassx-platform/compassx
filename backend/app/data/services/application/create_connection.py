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

def create_connection(db: Session, data: ConnectionCreate) -> CatalogConnection:
    import app.data.services.data_catalog_service as svc
    record = CatalogConnection(
        name=data.name,
        host=data.host,
        port=data.port,
        username=data.username,
        password_enc=svc.encrypt_password(data.password),
        default_database=data.default_database,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
