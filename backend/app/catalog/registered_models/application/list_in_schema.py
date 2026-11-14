from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.application.list_models import list_models
from app.catalog.registered_models.repository import _schema

def list_in_schema(db: Session, catalog_name: str, schema_name: str) -> list[CatalogRegisteredModel]:
    _schema(db, catalog_name, schema_name)
    return list_models(db, catalog_name, schema_name)

