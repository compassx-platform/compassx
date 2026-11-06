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

def get_connection(db: Session, conn_id: int) -> CatalogConnection | None:
    import app.data.services.data_catalog_service as svc
    return db.query(CatalogConnection).filter(CatalogConnection.id == conn_id).first()
