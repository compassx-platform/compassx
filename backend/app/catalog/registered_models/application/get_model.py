from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.artifacts import RegistryError
from app.catalog.registered_models.repository import _model_query

def get_model(db: Session, catalog_name: str, schema_name: str, name: str) -> CatalogRegisteredModel:
    model = (
        _model_query(db)
        .filter(
            CatalogRegisteredModel.catalog_name == catalog_name,
            CatalogRegisteredModel.schema_name == schema_name,
            CatalogRegisteredModel.name == name,
        )
        .first()
    )
    if model is None:
        raise RegistryError(404, f"Model '{catalog_name}.{schema_name}.{name}' was not found.")
    return model

