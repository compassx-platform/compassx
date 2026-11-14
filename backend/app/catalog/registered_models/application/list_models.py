from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.repository import _model_query

def list_models(db: Session, catalog_name: str | None = None, schema_name: str | None = None) -> list[CatalogRegisteredModel]:
    query = _model_query(db)
    if catalog_name:
        query = query.filter(CatalogRegisteredModel.catalog_name == catalog_name)
    if schema_name:
        query = query.filter(CatalogRegisteredModel.schema_name == schema_name)
    return query.order_by(CatalogRegisteredModel.full_name).all()

