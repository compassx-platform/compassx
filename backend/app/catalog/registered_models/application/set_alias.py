from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.models import CatalogModelAlias, CatalogRegisteredModel
from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.artifacts import RegistryError
from app.catalog.registered_models.schemas import ModelAliasSet
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor

def _set_alias(model: CatalogRegisteredModel, alias: str, version: int) -> None:
    known = {item.version for item in model.versions}
    if version not in known:
        raise RegistryError(404, f"Version {version} does not exist on '{model.full_name}'.")
    current = next((item for item in model.aliases if item.alias == alias), None)
    if current is None:
        model.aliases.append(CatalogModelAlias(alias=alias, version=version))
    else:
        current.version = version


def set_alias(db: Session, catalog_name: str, schema_name: str, name: str, body: ModelAliasSet, user: dict) -> CatalogRegisteredModel:
    model = get_model(db, catalog_name, schema_name, name)
    _set_alias(model, body.alias, body.version)
    model.updated_by = _current_actor(user)
    db.commit()
    return get_model(db, catalog_name, schema_name, name)

