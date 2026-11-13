"""HTTP API for models registered in the data catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.catalog.models import CatalogRegisteredModel
from app.catalog.registered_models.artifacts import RegistryError
from app.catalog.registered_models.schemas import (
    ModelAliasRead,
    ModelAliasSet,
    ModelCreate,
    ModelInvocation,
    ModelInvocationResult,
    ModelUpdate,
    ModelVersionCreate,
    ModelVersionRead,
    RegisteredModelRead,
    RegisteredModelSummary,
)
from app.catalog.registered_models.service import (
    create_model,
    delete_alias,
    delete_model,
    get_model,
    list_in_schema,
    list_models,
    register_version,
    set_alias,
    update_model,
)
from app.catalog.registered_models.serving import invoke_model
from app.database import get_account_db as get_db
from app.dependencies import get_current_user
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog Models"])


def _version_read(model: CatalogRegisteredModel, version) -> ModelVersionRead:
    aliases = [item.alias for item in model.aliases if item.version == version.version]
    return ModelVersionRead(
        version=version.version,
        run_id=version.run_id,
        source=version.source,
        artifact_path=version.artifact_path,
        status=version.status,
        comment=version.comment,
        storage_location=version.storage_location,
        files=list(version.files or []),
        metrics=dict(version.metrics or {}),
        params=dict(version.params or {}),
        aliases=aliases,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _read(model: CatalogRegisteredModel) -> RegisteredModelRead:
    versions = sorted(model.versions, key=lambda item: item.version, reverse=True)
    return RegisteredModelRead(
        id=model.id,
        catalog_name=model.catalog_name,
        schema_name=model.schema_name,
        name=model.name,
        full_name=model.full_name,
        comment=model.comment,
        owner=model.owner,
        storage_location=model.storage_location,
        created_at=model.created_at,
        updated_at=model.updated_at,
        created_by=model.created_by,
        updated_by=model.updated_by,
        aliases=[ModelAliasRead(alias=item.alias, version=item.version) for item in model.aliases],
        versions=[_version_read(model, version) for version in versions],
    )


def _summary(model: CatalogRegisteredModel) -> RegisteredModelSummary:
    latest = max((version.version for version in model.versions), default=None)
    return RegisteredModelSummary(
        id=model.id,
        catalog_name=model.catalog_name,
        schema_name=model.schema_name,
        name=model.name,
        full_name=model.full_name,
        comment=model.comment,
        owner=model.owner,
        updated_at=model.updated_at,
        latest_version=latest,
        aliases=[ModelAliasRead(alias=item.alias, version=item.version) for item in model.aliases],
    )


def _http(exc: RegistryError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/models", response_model=list[RegisteredModelSummary])
def get_registered_models(
    catalog: str | None = None,
    schema_name: str | None = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List registered models the caller may browse."""
    models = list_models(db, catalog, schema_name)
    visible = guard.filter(
        Privilege.BROWSE,
        models,
        lambda model: Securable.model(model.catalog_name, model.schema_name, model.name),
    )
    return [_summary(model) for model in visible]


@router.get(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models",
    response_model=list[RegisteredModelSummary],
)
def get_schema_models(
    catalog_name: str,
    schema_name: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    try:
        models = list_in_schema(db, catalog_name, schema_name)
    except RegistryError as exc:
        raise _http(exc) from exc
    visible = guard.filter(
        Privilege.BROWSE,
        models,
        lambda model: Securable.model(catalog_name, schema_name, model.name),
    )
    return [_summary(model) for model in visible]


@router.post(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models",
    response_model=RegisteredModelRead,
    status_code=201,
)
def add_registered_model(
    catalog_name: str,
    schema_name: str,
    body: ModelCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    """Create an empty registered model. Versions are added from MLflow runs."""
    guard.require(Privilege.CREATE, Securable.schema_(catalog_name, schema_name))
    try:
        model = create_model(db, catalog_name, schema_name, body.name, body.comment, user)
    except RegistryError as exc:
        raise _http(exc) from exc
    guard.claim_ownership(Securable.model(catalog_name, schema_name, model.name))
    return _read(model)


@router.get(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}",
    response_model=RegisteredModelRead,
)
def read_registered_model(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    guard.require(Privilege.BROWSE, Securable.model(catalog_name, schema_name, model_name))
    try:
        return _read(get_model(db, catalog_name, schema_name, model_name))
    except RegistryError as exc:
        raise _http(exc) from exc


@router.patch(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}",
    response_model=RegisteredModelRead,
)
def patch_registered_model(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    body: ModelUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    guard.require(Privilege.EDIT, Securable.model(catalog_name, schema_name, model_name))
    try:
        return _read(update_model(db, catalog_name, schema_name, model_name, body, user))
    except RegistryError as exc:
        raise _http(exc) from exc


@router.delete(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}",
    status_code=204,
)
def remove_registered_model(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    guard.require(Privilege.MANAGE, Securable.model(catalog_name, schema_name, model_name))
    try:
        delete_model(db, catalog_name, schema_name, model_name)
    except RegistryError as exc:
        raise _http(exc) from exc


@router.post(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}/versions",
    response_model=RegisteredModelRead,
    status_code=201,
)
async def add_model_version(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    body: ModelVersionCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    """Register a version from an MLflow run, creating the model on first use."""
    existing = (
        db.query(CatalogRegisteredModel)
        .filter(
            CatalogRegisteredModel.catalog_name == catalog_name,
            CatalogRegisteredModel.schema_name == schema_name,
            CatalogRegisteredModel.name == model_name,
        )
        .first()
    )
    if existing is None:
        guard.require(Privilege.CREATE, Securable.schema_(catalog_name, schema_name))
    else:
        guard.require(Privilege.EDIT, Securable.model(catalog_name, schema_name, model_name))
    try:
        result = await register_version(db, catalog_name, schema_name, model_name, body, user)
    except RegistryError as exc:
        db.rollback()
        raise _http(exc) from exc
    if result.created:
        guard.claim_ownership(Securable.model(catalog_name, schema_name, model_name))
    return _read(result.model)


@router.put(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}/aliases/{alias}",
    response_model=RegisteredModelRead,
)
def put_model_alias(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    alias: str,
    body: ModelAliasSet,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    """Point an alias at a version. The alias moves if it already exists."""
    if body.alias != alias:
        raise HTTPException(status_code=400, detail="The alias in the path and the body must match.")
    guard.require(Privilege.EDIT, Securable.model(catalog_name, schema_name, model_name))
    try:
        return _read(set_alias(db, catalog_name, schema_name, model_name, body, user))
    except RegistryError as exc:
        raise _http(exc) from exc


@router.delete(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}/aliases/{alias}",
    response_model=RegisteredModelRead,
)
def remove_model_alias(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    alias: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    guard: Guard = Depends(get_guard),
):
    guard.require(Privilege.EDIT, Securable.model(catalog_name, schema_name, model_name))
    try:
        return _read(delete_alias(db, catalog_name, schema_name, model_name, alias, user))
    except RegistryError as exc:
        raise _http(exc) from exc


def _version_for_invocation(model: CatalogRegisteredModel, body: ModelInvocation):
    if body.version is not None:
        match = next((item for item in model.versions if item.version == body.version), None)
        if match is None:
            raise RegistryError(404, f"Version {body.version} was not found.")
        return match
    alias_name = body.alias or "champion"
    alias = next((item for item in model.aliases if item.alias == alias_name), None)
    if alias is not None:
        match = next((item for item in model.versions if item.version == alias.version), None)
        if match is not None:
            return match
    ready = [item for item in model.versions if item.status == "READY"]
    if not ready:
        raise RegistryError(404, "The model has no ready version to score.")
    return max(ready, key=lambda item: item.version)


@router.post(
    "/catalogs/{catalog_name}/schemas/{schema_name}/models/{model_name}/invocations",
    response_model=ModelInvocationResult,
)
async def invoke_registered_model(
    catalog_name: str,
    schema_name: str,
    model_name: str,
    body: ModelInvocation,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Score records with a registered model. The artifact supplies its own feature contract."""
    guard.require(Privilege.EXECUTE, Securable.model(catalog_name, schema_name, model_name))
    try:
        model = get_model(db, catalog_name, schema_name, model_name)
        version = _version_for_invocation(model, body)
        predictions = await invoke_model(db, model, version, body.dataframe_records)
    except RegistryError as exc:
        raise _http(exc) from exc
    return ModelInvocationResult(model=model.full_name, version=version.version, predictions=predictions)
