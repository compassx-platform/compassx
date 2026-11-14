from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.repository import _index
from app.catalog.registered_models.schemas import ModelUpdate
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor

def update_model(db: Session, catalog_name: str, schema_name: str, name: str, body: ModelUpdate, user: dict) -> CatalogRegisteredModel:
    model = get_model(db, catalog_name, schema_name, name)
    if body.comment is not None:
        model.comment = body.comment
    if body.owner:
        model.owner = body.owner
    model.updated_by = _current_actor(user)
    _index(db, model)
    db.commit()
    return get_model(db, catalog_name, schema_name, name)

