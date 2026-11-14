from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.artifacts import RegistryError
from app.catalog.registered_models.repository import _index, _schema
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor

def create_model(db: Session, catalog_name: str, schema_name: str, name: str, comment: str | None, user: dict) -> CatalogRegisteredModel:
    schema = _schema(db, catalog_name, schema_name)
    existing = (
        db.query(CatalogRegisteredModel)
        .filter(
            CatalogRegisteredModel.catalog_name == catalog_name,
            CatalogRegisteredModel.schema_name == schema_name,
            CatalogRegisteredModel.name == name,
        )
        .first()
    )
    if existing is not None:
        raise RegistryError(409, f"Model '{catalog_name}.{schema_name}.{name}' already exists.")
    actor = _current_actor(user)
    model = CatalogRegisteredModel(
        schema_id=schema.id,
        catalog_name=catalog_name,
        schema_name=schema_name,
        name=name,
        comment=comment,
        owner=actor,
        storage_location=f"models/{name}",
        created_by=actor,
        updated_by=actor,
    )
    db.add(model)
    db.flush()
    _index(db, model)
    db.commit()
    return get_model(db, catalog_name, schema_name, name)

