from __future__ import annotations

import httpx
from dataclasses import dataclass
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalog.models import CatalogModelAlias, CatalogModelVersion, CatalogRegisteredModel
from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.artifacts import (
    RegistryError,
    artifact_paths,
    download_artifact,
    load_run,
    safe_artifact_relative,
    storage_relative,
)
from app.catalog.registered_models.repository import _index, _schema
from app.catalog.registered_models.schemas import ModelVersionCreate
from app.catalog.storage_context import resolve_catalog_storage
try:
    from app.catalog.shared.actor import _current_actor
except ImportError:  # older trees keep the helper on the catalog service module
    from app.catalog.service import _current_actor

@dataclass
class Registration:
    model: CatalogRegisteredModel
    version: CatalogModelVersion
    created: bool


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

