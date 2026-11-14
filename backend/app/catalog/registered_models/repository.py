"""Shared registered-model lookups. The log name stays the service logger."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session, selectinload

from app.catalog.models import CatalogRegisteredModel, UnifiedCatalog, UnifiedCatalogSchema
from app.catalog.registered_models.artifacts import RegistryError

logger = logging.getLogger("app.catalog.registered_models")


def _schema(db: Session, catalog_name: str, schema_name: str) -> UnifiedCatalogSchema:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if catalog is None:
        raise RegistryError(404, f"Catalog '{catalog_name}' was not found.")
    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if schema is None:
        raise RegistryError(404, f"Schema '{catalog_name}.{schema_name}' was not found.")
    return schema


def _model_query(db: Session):
    return db.query(CatalogRegisteredModel).options(
        selectinload(CatalogRegisteredModel.versions),
        selectinload(CatalogRegisteredModel.aliases),
    )


def _index(db: Session, model: CatalogRegisteredModel) -> None:
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding

        latest = max((version.version for version in model.versions), default=None)
        summary = f"Registered model {model.full_name}"
        if latest is not None:
            summary = f"{summary}, latest version {latest}"
        enqueue_asset_for_embedding(
            db,
            object_type="model",
            source_object_id=model.id,
            catalog_name=model.catalog_name,
            schema_name=model.schema_name,
            object_name=model.name,
            description=model.comment,
            content_summary=summary,
        )
    except Exception as exc:
        logger.warning("Failed to index registered model %s: %s", model.full_name, exc)

