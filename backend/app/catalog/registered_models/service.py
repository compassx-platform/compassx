"""Create, version, and alias registered models in the data catalog."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.catalog.models import (
    CatalogModelAlias,
    CatalogModelVersion,
    CatalogRegisteredModel,
    UnifiedCatalog,
    UnifiedCatalogSchema,
)
from app.catalog.registered_models.artifacts import (
    RegistryError,
    artifact_paths,
    download_artifact,
    load_run,
    safe_artifact_relative,
    storage_relative,
)
from app.catalog.registered_models.schemas import ModelAliasSet, ModelUpdate, ModelVersionCreate
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor
from app.catalog.storage_context import resolve_catalog_storage

logger = logging.getLogger("app.catalog.registered_models")

_NAME_PATTERN_MESSAGE = "Model names start with a letter and contain letters, numbers, '_' or '-'."


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


def list_models(db: Session, catalog_name: str | None = None, schema_name: str | None = None) -> list[CatalogRegisteredModel]:
    query = _model_query(db)
    if catalog_name:
        query = query.filter(CatalogRegisteredModel.catalog_name == catalog_name)
    if schema_name:
        query = query.filter(CatalogRegisteredModel.schema_name == schema_name)
    return query.order_by(CatalogRegisteredModel.full_name).all()


def list_in_schema(db: Session, catalog_name: str, schema_name: str) -> list[CatalogRegisteredModel]:
    _schema(db, catalog_name, schema_name)
    return list_models(db, catalog_name, schema_name)


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


@dataclass
class Registration:
    model: CatalogRegisteredModel
    version: CatalogModelVersion
    created: bool


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


def delete_model(db: Session, catalog_name: str, schema_name: str, name: str) -> None:
    model = get_model(db, catalog_name, schema_name, name)
    db.delete(model)
    db.commit()


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


def delete_alias(db: Session, catalog_name: str, schema_name: str, name: str, alias: str, user: dict) -> CatalogRegisteredModel:
    model = get_model(db, catalog_name, schema_name, name)
    current = next((item for item in model.aliases if item.alias == alias), None)
    if current is None:
        raise RegistryError(404, f"Alias '{alias}' is not set on '{model.full_name}'.")
    db.delete(current)
    model.updated_by = _current_actor(user)
    db.commit()
    return get_model(db, catalog_name, schema_name, name)


async def register_version(
    db: Session,
    catalog_name: str,
    schema_name: str,
    name: str,
    body: ModelVersionCreate,
    user: dict,
) -> Registration:
    schema = _schema(db, catalog_name, schema_name)
    artifact_path = safe_artifact_relative(body.artifact_path)
    actor = _current_actor(user)
    model = (
        db.query(CatalogRegisteredModel)
        .filter(
            CatalogRegisteredModel.catalog_name == catalog_name,
            CatalogRegisteredModel.schema_name == schema_name,
            CatalogRegisteredModel.name == name,
        )
        .first()
    )
    created = model is None
    if model is None:
        model = CatalogRegisteredModel(
            schema_id=schema.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=name,
            comment=body.comment,
            owner=actor,
            storage_location=f"models/{name}",
            created_by=actor,
            updated_by=actor,
        )
        db.add(model)
        db.flush()

    next_version = (
        db.query(func.max(CatalogModelVersion.version))
        .filter(CatalogModelVersion.model_id == model.id)
        .scalar()
        or 0
    ) + 1
    ctx = resolve_catalog_storage(db, catalog_name, schema_name)
    if ctx is None:
        raise RegistryError(400, f"Schema '{catalog_name}.{schema_name}' has no storage backend for model artifacts.")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        run = await load_run(client, body.run_id.strip())
        paths = await artifact_paths(client, body.run_id.strip(), artifact_path)
        stored: list[str] = []
        for path in paths:
            payload = await download_artifact(client, body.run_id.strip(), path)
            relative = storage_relative(name, next_version, path)
            await ctx.backend.write_bytes(ctx.rel_path(relative), payload, "application/octet-stream")
            stored.append(relative)

    source = f"runs:/{body.run_id.strip()}" + (f"/{artifact_path}" if artifact_path else "")
    version = CatalogModelVersion(
        model_id=model.id,
        version=next_version,
        run_id=body.run_id.strip(),
        source=source,
        artifact_path=artifact_path,
        status="READY",
        comment=body.comment,
        storage_location=storage_relative(name, next_version, ""),
        files=stored,
        metrics=run["metrics"],
        params=run["params"],
        created_by=actor,
    )
    db.add(version)
    db.flush()
    model.updated_by = actor
    if body.alias:
        existing_alias = (
            db.query(CatalogModelAlias)
            .filter(CatalogModelAlias.model_id == model.id, CatalogModelAlias.alias == body.alias)
            .first()
        )
        if existing_alias is None:
            db.add(CatalogModelAlias(model_id=model.id, alias=body.alias, version=next_version))
        else:
            existing_alias.version = next_version
    _index(db, model)
    db.commit()
    return Registration(get_model(db, catalog_name, schema_name, name), version, created)
