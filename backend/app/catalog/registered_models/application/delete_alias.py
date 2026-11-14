from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.artifacts import RegistryError
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor

def delete_alias(db: Session, catalog_name: str, schema_name: str, name: str, alias: str, user: dict) -> CatalogRegisteredModel:
    model = get_model(db, catalog_name, schema_name, name)
    current = next((item for item in model.aliases if item.alias == alias), None)
    if current is None:
        raise RegistryError(404, f"Alias '{alias}' is not set on '{model.full_name}'.")
    db.delete(current)
    model.updated_by = _current_actor(user)
    db.commit()
    return get_model(db, catalog_name, schema_name, name)

