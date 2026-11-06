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

def delete_connection(db: Session, conn_id: int) -> bool:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True
