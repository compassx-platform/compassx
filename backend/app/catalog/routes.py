from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Form, UploadFile, File, BackgroundTasks, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session


from app.catalog.schemas import (
    CatalogCreate,
    CatalogRead,
    CatalogSummary,
    CatalogTableRead,
    DataSourceProfileRead,
    LineageEdgeCreate,
    LineageGraphRead,
    RemoteDatabaseRead,
    RemoteSchemaRead,
    RemoteTableRead,
    SampleDataRead,
    SchemaCreate,
    SchemaRead,
    TableCreate,
    VolumeCreate,
    VolumeRead,
    VolumeResolveRequest,
    VolumeResolveResponse,
    NotebookCreate,
    NotebookRead,
    NotebookUpdate,
    NotebookMove,
    DashboardCreate,
    DashboardRead,
    DashboardUpdate,
    DashboardMove,
)
from app.catalog.service import (
    _to_table_read,
    browse_connection_databases,
    browse_connection_schemas,
    browse_connection_tables,
    create_catalog,
    create_schema,
    create_table,
    create_table_from_file,
    create_volume,
    delete_catalog,
    delete_schema,
    ensure_default_catalog,
    get_catalog_data_profile,
    get_schema_data_profile,
    get_data_profile,
    get_lineage,
    get_sample_data,
    get_table,
    list_catalogs,
    list_tables,
    refresh_columns,
    register_lineage,
    list_notebooks,
    get_notebook,
    create_notebook,
    update_notebook,
    move_notebook,
    delete_notebook,
    list_dashboards,
    get_dashboard,
    create_dashboard,
    update_dashboard,
    move_dashboard,
    delete_dashboard,
)
from app.database import get_account_db as get_db
from app.dependencies import get_current_user
from app.workspace.auth import validate_bearer_token

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


@router.get("/catalogs", response_model=list[CatalogSummary])
def read_catalogs(
    request: Request,
    db: Session = Depends(get_db),
):
    ensure_default_catalog(db)
    workspace_id = None
    workspace = getattr(request.state, "workspace", None)
    if workspace:
        workspace_id = workspace.workspace_id
    return list_catalogs(db, workspace_id=workspace_id)

@router.post("/catalogs", response_model=CatalogRead, status_code=201)
def add_catalog(
    request: Request,
    body: CatalogCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        catalog = create_catalog(db, body, user)
        
        # If there is an active workspace, automatically bind this catalog to it
        workspace = getattr(request.state, "workspace", None)
        if workspace:
            from app.catalog.models import CatalogWorkspaceBinding
            from app.catalog.schemas import CatalogPrivilege
            binding = CatalogWorkspaceBinding(
                catalog_id=catalog.id,
                workspace_id=workspace.workspace_id,
                privilege=CatalogPrivilege.READ_WRITE.value,
                is_default=False,
                bound_by=user.get("email") or user.get("id") or "system",
            )
            db.add(binding)
            db.commit()
            
        return catalog
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.delete("/catalogs/{catalog_name}", status_code=204)
def remove_catalog(
    catalog_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        delete_catalog(db, catalog_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class CatalogStorageUpdate(BaseModel):
    storage_backend_id: str | None = None
    base_path: str | None = None


@router.put("/catalogs/{catalog_name}/storage", response_model=CatalogRead)
def update_catalog_storage(
    catalog_name: str,
    body: CatalogStorageUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Set or clear the default storage backend for a catalog.
    All schemas / tables / volumes / notebooks under this catalog inherit
    this backend unless they have an explicit schema-level override.
    """
    from app.catalog.models import UnifiedCatalog
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise HTTPException(status_code=404, detail=f"Catalog '{catalog_name}' not found")
    catalog.storage_backend_id = body.storage_backend_id
    catalog.base_path = body.base_path
    db.commit()
    db.refresh(catalog)
    return catalog


class CatalogBindWorkspacesRequest(BaseModel):
    all_workspaces: bool
    workspace_ids: list[str] = []


@router.get("/catalogs/{catalog_name}/workspace-bindings")
def get_workspace_bindings(
    catalog_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        from app.catalog.binding_service import CatalogBindingService
        service = CatalogBindingService(db)
        return service.get_bindings(catalog_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/catalogs/{catalog_name}/workspace-bindings", status_code=200)
def update_workspace_bindings(
    catalog_name: str,
    body: CatalogBindWorkspacesRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        from app.catalog.binding_service import CatalogBindingService
        service = CatalogBindingService(db)
        bound_by = user.get("email") or user.get("id") or "admin"
        service.update_bindings(catalog_name, body.all_workspaces, body.workspace_ids, bound_by=bound_by)
        return {"status": "ok"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/sync", status_code=202)
def sync_catalog(
    catalog_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Sync a postgres catalog: walk information_schema, persist schemas/tables/columns,
    and enqueue embeddings. Runs in background; returns immediately."""
    from app.catalog.models import UnifiedCatalog
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise HTTPException(status_code=404, detail=f"Catalog '{catalog_name}' not found")
    if catalog.catalog_type != "postgres":
        raise HTTPException(status_code=400, detail="Sync is only supported for postgres catalogs")

    user_id = str(user.get("email") or user.get("sub") or user.get("id") or "system")

    def _run_sync() -> None:
        from app.database import AccountSessionLocal
        from app.catalog.service import sync_postgres_catalog
        sync_db = AccountSessionLocal()
        try:
            sync_postgres_catalog(sync_db, catalog_name, triggered_by=user_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Postgres catalog sync failed for '%s': %s", catalog_name, exc, exc_info=True)
        finally:
            sync_db.close()

    background_tasks.add_task(_run_sync)
    return {"status": "queued", "catalog_name": catalog_name}


@router.delete("/catalogs/{catalog_name}/schemas/{schema_name}", status_code=204)
def remove_schema(
    catalog_name: str,
    schema_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a schema from the catalog. Blocked if the schema contains notebooks."""
    try:
        delete_schema(db, catalog_name, schema_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas", response_model=SchemaRead, status_code=201)
def add_schema(
    catalog_name: str,
    body: SchemaCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        return create_schema(db, catalog_name, body, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/tables", response_model=CatalogTableRead, status_code=201)
def add_table(
    catalog_name: str,
    schema_name: str,
    body: TableCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        table = create_table(db, catalog_name, schema_name, body, user)
        return _to_table_read(table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/tables-from-file", response_model=CatalogTableRead, status_code=201)
async def add_table_from_file(
    catalog_name: str,
    schema_name: str,
    table_name: str = Form(...),
    description: str | None = Form(default=None),
    columns_json: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    import json
    try:
        columns = json.loads(columns_json)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid columns JSON: {exc}")
    try:
        file_bytes = await file.read()
        table = await create_table_from_file(
            db=db,
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_name=table_name,
            description=description,
            columns=columns,
            file_name=file.filename or "data.csv",
            file_bytes=file_bytes,
            user=user,
        )
        return _to_table_read(table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/iceberg/repair-version-hints", status_code=200)
async def repair_iceberg_version_hints(db: Session = Depends(get_db)):
    """
    Backfill version-hint.text for all Iceberg tables missing it.
    DuckDB requires this file to locate the current metadata version.
    Safe to run multiple times (idempotent).
    """
    from app.catalog.models import CatalogTableType, UnifiedCatalogSchema, UnifiedCatalogTable
    from app.catalog.storage_context import resolve_catalog_storage_by_schema_id

    tables = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .filter(UnifiedCatalogTable.table_type == CatalogTableType.ICEBERG)
        .all()
    )

    repaired, already_ok, errors = [], [], []

    for table in tables:
        ctx = resolve_catalog_storage_by_schema_id(db, table.schema_id)
        if not ctx:
            already_ok.append(table.name)
            continue

        table_dir_rel = ""
        if table.storage_location:
            # storage_location is absolute; strip backend_base to get relative
            loc = table.storage_location.strip("/")
            pfx = ctx.backend_base.strip("/")
            table_dir_rel = loc[len(pfx) + 1:] if loc.startswith(pfx) else loc
        elif table.metadata_location:
            loc = table.metadata_location.strip("/")
            if "/metadata/" in loc:
                loc = loc.split("/metadata/")[0]
            pfx = ctx.backend_base.strip("/")
            table_dir_rel = loc[len(pfx) + 1:] if loc.startswith(pfx) else loc

        if not table_dir_rel:
            already_ok.append(table.name)
            continue

        hint_path = f"{table_dir_rel.rstrip('/')}/metadata/version-hint.text"
        try:
            if not await ctx.backend.exists(hint_path):
                await ctx.backend.write_bytes(path=hint_path, data=b"1", content_type="text/plain")
                repaired.append(table.name)
            else:
                already_ok.append(table.name)
        except Exception as exc:
            errors.append({"table": table.name, "error": str(exc)})

    return {"repaired": repaired, "already_ok": already_ok, "errors": errors}


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/volumes", response_model=VolumeRead, status_code=201)
async def add_volume(
    catalog_name: str,
    schema_name: str,
    body: VolumeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        return await create_volume(db, catalog_name, schema_name, body, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tables", response_model=list[CatalogTableRead])
def read_tables(
    catalog: str | None = Query(default=None),
    schema_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_tables(db, catalog=catalog, schema_name=schema_name)


@router.get("/volumes", response_model=list[VolumeRead])
def read_volumes(
    catalog: str | None = Query(default=None),
    schema_name: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    from app.catalog.service import list_volumes
    return list_volumes(db, catalog=catalog, schema_name=schema_name)



@router.get("/tables/{catalog}/{schema_name}/{table_name}", response_model=CatalogTableRead)
def read_table(catalog: str, schema_name: str, table_name: str, db: Session = Depends(get_db)):
    try:
        return get_table(db, f"{catalog}.{schema_name}.{table_name}")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))



@router.get("/tables/{catalog}/{schema_name}/{table_name}/sample-data", response_model=SampleDataRead)
def read_sample_data(
    catalog: str,
    schema_name: str,
    table_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return get_sample_data(db, f"{catalog}.{schema_name}.{table_name}", limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/tables/{catalog}/{schema_name}/{table_name}/refresh-columns", response_model=CatalogTableRead)
def refresh_table_columns(
    catalog: str,
    schema_name: str,
    table_name: str,
    db: Session = Depends(get_db),
):
    try:
        return refresh_columns(db, f"{catalog}.{schema_name}.{table_name}")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/tables/{catalog}/{schema_name}/{table_name}/data-profile", response_model=DataSourceProfileRead | None)
def read_data_profile(
    catalog: str,
    schema_name: str,
    table_name: str,
    db: Session = Depends(get_db),
):
    """Return the AI-inferred data profile for a table, or null if not yet profiled."""
    return get_data_profile(db, f"{catalog}.{schema_name}.{table_name}")


@router.get("/catalogs/{catalog}/data-profile", response_model=DataSourceProfileRead | None)
def read_catalog_data_profile(
    catalog: str,
    db: Session = Depends(get_db),
):
    """Return the AI-inferred data profile for a catalog, or null if not yet profiled."""
    return get_catalog_data_profile(db, catalog)


@router.get("/schemas/{catalog}/{schema_name}/data-profile", response_model=DataSourceProfileRead | None)
def read_schema_data_profile(
    catalog: str,
    schema_name: str,
    db: Session = Depends(get_db),
):
    """Return the AI-inferred data profile for a schema, or null if not yet profiled."""
    return get_schema_data_profile(db, catalog, schema_name)


def _queue_catalog_profiling(
    *, catalog: str, schema_name: str | None, table_name: str | None,
    background_tasks: BackgroundTasks, db: Session, user: dict,
) -> dict:
    """Resolve profiling infrastructure from a catalog asset and queue its profiler."""
    from app.agents.models.agents import DBConnection
    from app.agents.routes.db_connection_routes import trigger_profiling
    from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTable

    catalog_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog).first()
    if not catalog_model:
        raise HTTPException(status_code=404, detail=f"Catalog '{catalog}' not found")

    connection_id = catalog_model.connection_id
    physical_table = table_name
    if schema_name:
        schema_model = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog_model.id,
            UnifiedCatalogSchema.name == schema_name,
        ).first()
        if not schema_model:
            raise HTTPException(status_code=404, detail=f"Schema '{catalog}.{schema_name}' not found")
        if table_name:
            table_model = db.query(UnifiedCatalogTable).filter(
                UnifiedCatalogTable.schema_id == schema_model.id,
                UnifiedCatalogTable.name == table_name,
            ).first()
            if table_model:
                connection_id = table_model.connection_id or connection_id
                physical_table = table_model.pg_table or table_model.name
            elif catalog_model.catalog_type != "postgres":
                raise HTTPException(status_code=404, detail=f"Table '{catalog}.{schema_name}.{table_name}' not found")

    target_type = "table" if table_name else ("schema" if schema_name else "catalog")
    if catalog_model.catalog_type == "iceberg":
        async def run_iceberg_profile() -> None:
            from app.catalog.profiling import profile_iceberg_scope
            from app.database import SessionLocal

            background_db = SessionLocal()
            try:
                await profile_iceberg_scope(
                    background_db, catalog_name=catalog, schema_name=schema_name, table_name=table_name,
                )
            finally:
                background_db.close()

        background_tasks.add_task(run_iceberg_profile)
        return {"status": "queued", "target": target_type, "catalog": catalog, "schema": schema_name, "table": table_name}

    if not connection_id:
        raise HTTPException(status_code=400, detail="This catalog asset has no profileable database connection")
    from app.database import AccountSessionLocal
    sys_db = AccountSessionLocal()
    try:
        connection = sys_db.query(DBConnection).filter(DBConnection.id == connection_id).first()
        if connection:
            sys_db.expunge(connection)
    finally:
        sys_db.close()
    if not connection:
        raise HTTPException(status_code=400, detail="The catalog asset's database connection is unavailable")
    if not connection.profiler_agent_id:
        raise HTTPException(status_code=400, detail="No profiler agent is configured for this catalog's connection")

    scope = {"target_type": target_type, "catalog_name": catalog}
    if schema_name:
        scope["schema_name"] = schema_name
    if physical_table:
        scope["table_name"] = physical_table
    trigger_profiling(
        connection,
        user.get("id") or user.get("sub") or "default_user",
        user.get("org_id") or "default",
        background_tasks,
        catalog_scope=scope,
    )
    return {"status": "queued", "target": target_type, "catalog": catalog, "schema": schema_name, "table": table_name}


@router.post("/catalogs/{catalog}/profile", status_code=202)
def profile_catalog(catalog: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _queue_catalog_profiling(catalog=catalog, schema_name=None, table_name=None, background_tasks=background_tasks, db=db, user=user)


@router.post("/catalogs/{catalog}/schemas/{schema_name}/profile", status_code=202)
def profile_schema(catalog: str, schema_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _queue_catalog_profiling(catalog=catalog, schema_name=schema_name, table_name=None, background_tasks=background_tasks, db=db, user=user)


@router.post("/catalogs/{catalog}/schemas/{schema_name}/tables/{table_name}/profile", status_code=202)
def profile_table(catalog: str, schema_name: str, table_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _queue_catalog_profiling(catalog=catalog, schema_name=schema_name, table_name=table_name, background_tasks=background_tasks, db=db, user=user)


@router.post("/lineage", status_code=201)
def add_lineage(
    body: LineageEdgeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        register_lineage(db, body, user)
        return {"status": "ok"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/lineage/{catalog}/{schema_name}/{table_name}", response_model=LineageGraphRead)
def read_lineage(catalog: str, schema_name: str, table_name: str, db: Session = Depends(get_db)):
    try:
        return get_lineage(db, f"{catalog}.{schema_name}.{table_name}")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/connections/{connection_id}/browse/databases", response_model=list[RemoteDatabaseRead])
def read_remote_databases(connection_id: int, db: Session = Depends(get_db)):
    try:
        return browse_connection_databases(db, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/connections/{connection_id}/browse/schemas", response_model=list[RemoteSchemaRead])
def read_remote_schemas(connection_id: int, database: str, db: Session = Depends(get_db)):
    try:
        return browse_connection_schemas(db, connection_id, database)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/connections/{connection_id}/browse/tables", response_model=list[RemoteTableRead])
def read_remote_tables(connection_id: int, database: str, schema_name: str, db: Session = Depends(get_db)):
    try:
        return browse_connection_tables(db, connection_id, database, schema_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Iceberg — schema creation with blob storage
# ---------------------------------------------------------------------------

@router.post("/iceberg/schemas", status_code=201)
async def create_iceberg_schema_endpoint(
    catalog: str,
    schema_name: str,
    storage_backend: str,
    description: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Create an Iceberg schema bound to a storage backend.
    Writes a .schema marker file to blob storage and sets base_path on the schema row.
    """
    from app.catalog.service import create_iceberg_schema
    try:
        return await create_iceberg_schema(
            db=db,
            catalog_name=catalog,
            schema_name=schema_name,
            storage_backend_name=storage_backend,
            user=user,
            description=description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class IcebergTableCreate(BaseModel):
    catalog: str
    schema_name: str
    table_name: str
    columns: list[dict]
    description: str | None = None
    properties: dict = {}


@router.post("/iceberg/tables", response_model=CatalogTableRead, status_code=201)
async def create_iceberg_table_endpoint(
    payload: IcebergTableCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Create an Iceberg table — writes v1.metadata.json + data/.keep to blob storage,
    then registers the table in the catalog with metadata_location.
    """
    from app.catalog.service import create_iceberg_table
    try:
        return await create_iceberg_table(
            db=db,
            catalog_name=payload.catalog,
            schema_name=payload.schema_name,
            table_name=payload.table_name,
            columns=payload.columns,
            user=user,
            description=payload.description,
            properties=payload.properties,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Volume file operations
# ---------------------------------------------------------------------------

from fastapi import UploadFile, File, Body
from fastapi.responses import Response
from app.storage.models import FileInfo


def _get_volume_manager(db: Session, volume_id: str):
    """Resolve the correct storage backend for a volume and return a VolumeManager."""
    from app.catalog.models import UnifiedCatalogVolume
    from app.catalog.storage_context import resolve_catalog_storage_by_schema_id
    from app.catalog.volume_manager import VolumeManager

    volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
    if not volume:
        raise ValueError(f"Volume '{volume_id}' not found")

    ctx = resolve_catalog_storage_by_schema_id(db, volume.schema_id)
    if not ctx:
        raise ValueError("No storage backend configured for this volume's schema or parent catalog")

    return VolumeManager(ctx.backend, ctx.backend_base)



@router.post("/volumes/{volume_id}/files", response_model=FileInfo, status_code=201)
async def upload_volume_file(
    volume_id: str,
    file: UploadFile = File(...),
    sub_path: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upload a file to a volume on blob storage and index it in Postgres."""
    try:
        manager = _get_volume_manager(db, volume_id)
        data = await file.read()
        actor = user.get("email", user.get("id", "unknown"))
        return await manager.upload_file(
            db=db, volume_id=volume_id, file_name=file.filename,
            data=data, sub_path=sub_path, uploaded_by=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/volumes/{volume_id}/directories", response_model=FileInfo, status_code=201)
async def create_volume_directory(
    volume_id: str,
    dir_name: str = Body(..., embed=True),
    sub_path: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a directory in a volume on blob storage and index it in Postgres."""
    try:
        manager = _get_volume_manager(db, volume_id)
        actor = user.get("email", user.get("id", "unknown"))
        return await manager.create_directory(
            db=db, volume_id=volume_id, dir_name=dir_name, sub_path=sub_path, uploaded_by=actor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/volumes/{volume_id}/files", response_model=list[FileInfo])
async def list_volume_files(volume_id: str, db: Session = Depends(get_db)):
    """List all files in a volume from blob storage."""
    try:
        manager = _get_volume_manager(db, volume_id)
        return await manager.list_files(db, volume_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class RecordFileRequest(BaseModel):
    catalog: str
    schema_name: str
    volume_name: str
    file_path: str


@router.post("/volumes/record-file", status_code=201)
async def record_volume_file(
    body: RecordFileRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Index a file written from a notebook client in Postgres."""
    import logging
    logger = logging.getLogger(__name__)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    try:
        token = authorization[7:]
        principal = validate_bearer_token(token)
        user_id = principal.id if hasattr(principal, "id") else principal.get("sub")
    except Exception as exc:
        logger.warning("Volume record-file: token validation failed: %s", exc)
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(exc)}")

    try:
        from app.catalog.models import UnifiedCatalogVolume, UnifiedCatalogSchema, UnifiedCatalog
        from app.catalog.db_models import UnifiedCatalogVolumeFile
        from app.catalog.storage_context import resolve_catalog_storage
        from datetime import datetime, timezone

        # Find schema and catalog
        schema = db.query(UnifiedCatalogSchema).join(
            UnifiedCatalog,
            UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id,
        ).filter(
            UnifiedCatalog.name == body.catalog,
            UnifiedCatalogSchema.name == body.schema_name,
        ).first()

        if not schema:
            raise HTTPException(status_code=404, detail=f"Schema '{body.catalog}.{body.schema_name}' not found")

        # Find volume
        volume = db.query(UnifiedCatalogVolume).filter(
            UnifiedCatalogVolume.schema_id == schema.id,
            UnifiedCatalogVolume.name == body.volume_name,
        ).first()

        if not volume:
            raise HTTPException(status_code=404, detail=f"Volume '{body.catalog}.{body.schema_name}.{body.volume_name}' not found")

        # Resolve storage backend
        storage_ctx = resolve_catalog_storage(db, body.catalog, body.schema_name)
        if not storage_ctx:
            raise HTTPException(status_code=500, detail="Storage backend not configured for volume")

        backend = storage_ctx.backend

        # Compute file prefix in backend
        container_name = backend.container
        backend_base = (storage_ctx.backend_base or "").strip("/")
        
        volume_loc = (volume.storage_location or "").strip("/")
        if volume_loc:
            if volume_loc.startswith(container_name + "/"):
                volume_prefix = volume_loc
            else:
                volume_prefix = f"{container_name}/{volume_loc}"
        else:
            if backend_base:
                volume_prefix = f"{container_name}/{backend_base}/{schema.catalog.name}/{schema.name}/volumes/{volume.name}"
            else:
                volume_prefix = f"{container_name}/{schema.catalog.name}/{schema.name}/volumes/{volume.name}"
            
        abs_path = f"{volume_prefix.rstrip('/')}/{body.file_path.lstrip('/')}"

        # Strip container and backend base_path to get relative path for backend methods
        path_in_container = abs_path.removeprefix(container_name).lstrip("/")
        backend_base_dir = (storage_ctx.backend_base or "").rstrip("/") + "/"
        backend_rel = path_in_container.removeprefix(backend_base_dir)

        # Get file metadata
        raw_files = await backend.list_files(backend_rel)
        size_bytes = 0
        import mimetypes
        content_type = mimetypes.guess_type(body.file_path)[0] or "application/octet-stream"
        
        if raw_files:
            match = next((f for f in raw_files if f.file_path == backend_rel), raw_files[0])
            size_bytes = match.size_bytes
            content_type = match.content_type or content_type

        # Update or create DB record
        file_relative = body.file_path.lstrip("/")
        file_name = file_relative.split("/")[-1]
        
        existing = (
            db.query(UnifiedCatalogVolumeFile)
            .filter(
                UnifiedCatalogVolumeFile.volume_id == volume.id,
                UnifiedCatalogVolumeFile.file_path == file_relative,
            )
            .first()
        )

        if existing:
            existing.size_bytes = size_bytes
            existing.content_type = content_type
            existing.uploaded_by = str(user_id)
            existing.uploaded_at = datetime.now(timezone.utc)
        else:
            entry = UnifiedCatalogVolumeFile(
                volume_id=volume.id,
                file_path=file_relative,
                file_name=file_name,
                size_bytes=size_bytes,
                content_type=content_type,
                uploaded_by=str(user_id),
            )
            db.add(entry)
        db.commit()
        
        logger.info(
            "Volume record-file: recorded %s in volume %s (%d bytes)",
            file_relative, volume.id, size_bytes
        )
        return {"status": "success", "file_path": file_relative, "size_bytes": size_bytes}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Volume record-file unexpected error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volumes/{volume_id}/files/rename", response_model=FileInfo)
async def rename_volume_file(
    volume_id: str,
    old_path: str = Body(..., embed=True),
    new_name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Rename a file or directory in a volume."""
    try:
        manager = _get_volume_manager(db, volume_id)
        return await manager.rename_file(db, volume_id, old_path, new_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/volumes/{volume_id}/files/download")
async def download_volume_file(volume_id: str, file_path: str, db: Session = Depends(get_db)):
    """Download a file from a volume."""
    try:
        manager = _get_volume_manager(db, volume_id)
        data, content_type = await manager.download_file(db, volume_id, file_path)
        return Response(content=data, media_type=content_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/volumes/{volume_id}/files/url")
async def get_volume_file_url(
    volume_id: str, file_path: str, expiry_seconds: int = 3600, db: Session = Depends(get_db)
):
    """Get a presigned/SAS URL for temporary direct access to a volume file."""
    try:
        manager = _get_volume_manager(db, volume_id)
        url = await manager.get_download_url(db, volume_id, file_path, expiry_seconds)
        return {"url": url, "expires_in_seconds": expiry_seconds}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/volumes/{volume_id}/files", status_code=204)
async def delete_volume_file(
    volume_id: str, file_path: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a file from a volume on blob storage and remove its index entry."""
    try:
        manager = _get_volume_manager(db, volume_id)
        await manager.delete_file(db, volume_id, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Notebooks ─────────────────────────────────────────────────────────────────

@router.get("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks", response_model=list[NotebookRead])
def get_notebooks(
    catalog_name: str,
    schema_name: str,
    db: Session = Depends(get_db)
):
    """List notebooks registered under a schema."""
    try:
        return list_notebooks(db, catalog_name, schema_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks", response_model=NotebookRead, status_code=201)
async def add_notebook(
    catalog_name: str,
    schema_name: str,
    body: NotebookCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Register and create a new notebook in a schema."""
    try:
        return await create_notebook(db, catalog_name, schema_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks/{notebook_name}", response_model=NotebookRead)
def read_notebook(
    catalog_name: str,
    schema_name: str,
    notebook_name: str,
    db: Session = Depends(get_db)
):
    """Retrieve notebook metadata."""
    try:
        return get_notebook(db, catalog_name, schema_name, notebook_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks/{notebook_name}", response_model=NotebookRead)
def rename_notebook(
    catalog_name: str,
    schema_name: str,
    notebook_name: str,
    body: NotebookUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update notebook metadata (rename, change comment or owner)."""
    try:
        return update_notebook(db, catalog_name, schema_name, notebook_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks/{notebook_name}/move", response_model=NotebookRead)
async def move_catalog_notebook(
    catalog_name: str,
    schema_name: str,
    notebook_name: str,
    body: NotebookMove,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Move a notebook to another catalog and/or schema (and optionally rename it)."""
    try:
        return await move_notebook(db, catalog_name, schema_name, notebook_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks/{notebook_name}", status_code=204)
async def remove_notebook(
    catalog_name: str,
    schema_name: str,
    notebook_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a notebook registration and its physical file."""
    try:
        await delete_notebook(db, catalog_name, schema_name, notebook_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Dashboards ────────────────────────────────────────────────────────────────

@router.get("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards", response_model=list[DashboardRead])
def get_dashboards(
    catalog_name: str,
    schema_name: str,
    db: Session = Depends(get_db)
):
    """List dashboards registered under a schema."""
    try:
        return list_dashboards(db, catalog_name, schema_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards", response_model=DashboardRead, status_code=201)
async def add_dashboard(
    catalog_name: str,
    schema_name: str,
    body: DashboardCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Register and create a new dashboard in a schema."""
    try:
        return await create_dashboard(db, catalog_name, schema_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards/{dashboard_name}", response_model=DashboardRead)
def read_dashboard(
    catalog_name: str,
    schema_name: str,
    dashboard_name: str,
    db: Session = Depends(get_db)
):
    """Retrieve dashboard metadata."""
    try:
        return get_dashboard(db, catalog_name, schema_name, dashboard_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards/{dashboard_name}", response_model=DashboardRead)
def rename_dashboard(
    catalog_name: str,
    schema_name: str,
    dashboard_name: str,
    body: DashboardUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update dashboard metadata (rename, change comment or owner)."""
    try:
        return update_dashboard(db, catalog_name, schema_name, dashboard_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards/{dashboard_name}/move", response_model=DashboardRead)
async def move_catalog_dashboard(
    catalog_name: str,
    schema_name: str,
    dashboard_name: str,
    body: DashboardMove,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Move a dashboard to another catalog and/or schema (and optionally rename it)."""
    try:
        return await move_dashboard(db, catalog_name, schema_name, dashboard_name, body, user)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/catalogs/{catalog_name}/schemas/{schema_name}/dashboards/{dashboard_name}", status_code=204)
async def remove_dashboard(
    catalog_name: str,
    schema_name: str,
    dashboard_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a dashboard registration and its system database entry."""
    try:
        await delete_dashboard(db, catalog_name, schema_name, dashboard_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))



@router.post("/catalogs/{catalog_name}/schemas/{schema_name}/notebooks/{notebook_name}/run")
async def run_catalog_notebook(
    catalog_name: str,
    schema_name: str,
    notebook_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Run/Execute a catalog notebook, executing its Python code cells and updating outputs."""
    import json
    import io
    import sys
    import traceback
    from app.catalog.models import UnifiedCatalogSchema
    from app.catalog.service import _notebook_exists, _read_notebook_content, _write_notebook_content

    try:
        notebook = get_notebook(db, catalog_name, schema_name, notebook_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Notebook schema not found.")

    if not await _notebook_exists(db, schema, notebook.blob_path):
        raise HTTPException(status_code=404, detail="Notebook file not found in storage.")

    try:
        nb = await _read_notebook_content(db, schema, notebook.blob_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read notebook JSON: {exc}")

    cells = nb.get("cells", [])
    exec_globals = {}
    from contextlib import redirect_stdout, redirect_stderr

    for cell in cells:
        if cell.get("cell_type") != "code":
            continue

        cell["outputs"] = []
        cell["execution_count"] = cell.get("execution_count", 0) + 1

        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        if not source.strip():
            continue

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                compiled_code = compile(source, filename=f"<{notebook_name}-cell>", mode="exec")
                exec(compiled_code, exec_globals)

            stdout_val = stdout_buf.getvalue()
            stderr_val = stderr_buf.getvalue()

            if stdout_val:
                cell["outputs"].append({
                    "output_type": "stream",
                    "name": "stdout",
                    "text": stdout_val.splitlines(keepends=True)
                })
            if stderr_val:
                cell["outputs"].append({
                    "output_type": "stream",
                    "name": "stderr",
                    "text": stderr_val.splitlines(keepends=True)
                })
        except Exception as e:
            stdout_val = stdout_buf.getvalue()
            stderr_val = stderr_buf.getvalue()

            if stdout_val:
                cell["outputs"].append({
                    "output_type": "stream",
                    "name": "stdout",
                    "text": stdout_val.splitlines(keepends=True)
                })
            if stderr_val:
                cell["outputs"].append({
                    "output_type": "stream",
                    "name": "stderr",
                    "text": stderr_val.splitlines(keepends=True)
                })

            tb_lines = traceback.format_exception(*sys.exc_info())
            cell["outputs"].append({
                "output_type": "error",
                "ename": type(e).__name__,
                "evalue": str(e),
                "traceback": tb_lines
            })
            break

    try:
        await _write_notebook_content(db, schema, notebook.blob_path, nb)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write updated notebook to storage: {exc}")

    return {
        "status": "success",
        "notebook": NotebookRead.model_validate(notebook),
        "cells": cells
    }


@router.post("/admin/import-notebooks", status_code=200)
def import_notebooks(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Scan the notebooks storage and register any untracked .ipynb files in the unified catalog under compassx.default."""
    import re
    from services.storage.fs import get_fs
    from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _NOTEBOOKS_PREFIX, _key_to_rel
    from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogNotebook

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == "compassx").first()
    if not catalog:
        catalog = UnifiedCatalog(name="compassx", description="Default CompassX catalog", created_by="system")
        db.add(catalog)
        db.commit()
        db.refresh(catalog)

    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == "default"
    ).first()
    if not schema:
        schema = UnifiedCatalogSchema(
            catalog_id=catalog.id,
            name="default",
            description="Default schema",
            created_by="system"
        )
        db.add(schema)
        db.commit()
        db.refresh(schema)

    fs = get_fs()
    prefix = _NOTEBOOKS_PREFIX + "/" if _NOTEBOOKS_PREFIX else ""
    try:
        keys = fs.list_objects(_NOTEBOOKS_BUCKET, prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan storage: {e}")

    imported = []
    skipped = []

    for key in keys:
        if not key.endswith(".ipynb"):
            continue
        
        rel_path = _key_to_rel(key)
        
        existing = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.blob_path == rel_path
        ).first()
        if existing:
            skipped.append(rel_path)
            continue
        
        base_name = rel_path.rsplit("/", 1)[-1].removesuffix(".ipynb")
        sanitized_name = re.sub(r"[^a-zA-Z0-9_]", "_", base_name)
        if not sanitized_name:
            sanitized_name = "untitled_notebook"
            
        name_candidate = sanitized_name
        counter = 1
        while db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.schema_id == schema.id,
            UnifiedCatalogNotebook.name == name_candidate
        ).first():
            name_candidate = f"{sanitized_name}_{counter}"
            counter += 1

        notebook = UnifiedCatalogNotebook(
            schema_id=schema.id,
            catalog_name="compassx",
            schema_name="default",
            name=name_candidate,
            blob_path=rel_path,
            owner="system",
            comment="Automatically imported during admin scan",
            created_by="system",
            updated_by="system"
        )
        db.add(notebook)
        imported.append({"name": name_candidate, "blob_path": rel_path})

    db.commit()
    return {"status": "success", "imported": imported, "skipped_count": len(skipped)}


# ── Semantic Search / Foreign Catalog Sync ────────────────────────────────────

class ForeignSyncRequest(BaseModel):
    foreign_catalog_name: str


@router.post("/connections/{connection_id}/sync-foreign", status_code=202)
def trigger_foreign_sync(
    connection_id: int,
    body: ForeignSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Trigger an asynchronous sync of a foreign Postgres catalog into the
    semantic search index.

    The sync queries ``information_schema`` on the external database and
    upserts rows into ``vector_db.assets`` with ``is_foreign=True``.
    Each newly-synced table is enqueued for embedding.
    """
    from app.database import AccountSessionLocal

    user_id = str(user.get("id") or user.get("sub") or "unknown")
    foreign_catalog_name = body.foreign_catalog_name

    def _run_sync() -> None:
        sync_db = AccountSessionLocal()
        try:
            from app.catalog.foreign_sync import sync_foreign_catalog
            sync_foreign_catalog(
                sync_db,
                connection_id=connection_id,
                foreign_catalog_name=foreign_catalog_name,
                triggered_by_user_id=user_id,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "Foreign catalog sync background task failed: %s", exc, exc_info=True
            )
        finally:
            sync_db.close()

    background_tasks.add_task(_run_sync)
    return {
        "status": "queued",
        "connection_id": connection_id,
        "foreign_catalog_name": foreign_catalog_name,
    }


@router.get("/connections/{connection_id}/foreign-sync-log")
def get_foreign_sync_log(
    connection_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return recent foreign catalog sync log entries for a connection."""
    from app.catalog.search_models import CatalogSearchForeignSyncLog

    rows = (
        db.query(CatalogSearchForeignSyncLog)
        .filter(CatalogSearchForeignSyncLog.connection_id == connection_id)
        .order_by(CatalogSearchForeignSyncLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "foreign_catalog_name": r.foreign_catalog_name,
            "connection_id": r.connection_id,
            "triggered_by_user_id": r.triggered_by_user_id,
            "status": r.status,
            "tables_synced": r.tables_synced,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in rows
    ]


@router.get("/search")
def search_catalog_assets(
    q: str = Query(..., description="Natural language search query"),
    object_type: str | None = Query(default=None, description="Filter by object type"),
    limit: int = Query(default=10, ge=1, le=25),
):
    """REST endpoint for catalog semantic search.

    Embeds *q* and returns the top *limit* catalog assets ranked by
    cosine similarity.  This is a thin HTTP wrapper around the same logic
    used by the ``search_assets`` agent tool.
    """
    from app.catalog.embedding_service import get_embedding
    from app.database import account_engine
    from sqlalchemy import text as sa_text

    if object_type == "all":
        object_type = None

    query_vec = get_embedding(q)
    if query_vec is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable. Ensure an LLM connection is marked 'use_for_embedding' and configured.",
        )

    _SEARCH_SQL = """
        SELECT
            catalog_name || '.' || schema_name || '.' || object_name AS full_name,
            object_type,
            description,
            is_foreign,
            1 - (embedding <=> :query_vec ::vector) AS similarity_score
        FROM vector_db.assets
        WHERE embedding IS NOT NULL
          AND (:object_type_filter ::text IS NULL OR object_type = :object_type_filter)
        ORDER BY embedding <=> :query_vec ::vector
        LIMIT :limit
    """

    vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
    try:
        with account_engine.connect() as conn:
            rows = conn.execute(
                sa_text(_SEARCH_SQL),
                {
                    "query_vec": vec_literal,
                    "object_type_filter": object_type,
                    "limit": limit,
                },
            ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    return {
        "query": q,
        "results": [
            {
                "full_name": row.full_name,
                "object_type": row.object_type,
                "description": row.description,
                "is_foreign": row.is_foreign,
                "similarity_score": round(float(row.similarity_score), 4),
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/volumes/resolve", response_model=VolumeResolveResponse, status_code=200)
async def resolve_volume_credential(
    req_context: Request,
    body: VolumeResolveRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Resolve volume access credentials for notebook kernel.

    Validates:
    1. Session token (Bearer JWT from Authorization header)
    2. Volume exists and is visible to workspace
    3. User has READ privilege on catalog/schema containing volume

    Returns scoped credentials (SAS, STS, or presigned URL) for the volume prefix.
    """
    import logging
    from app.catalog.storage_context import resolve_catalog_storage
    from app.storage.factory import build_backend

    logger = logging.getLogger(__name__)

    # Extract and validate token
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "TOKEN_INVALID_OR_EXPIRED",
                "message": "Missing or invalid Authorization header",
            },
        )

    try:
        token = authorization[7:]  # Remove "Bearer " prefix
        principal = validate_bearer_token(token)
        user_id = principal.id if hasattr(principal, "id") else principal.get("sub")
        workspace_id = req_context.state.workspace.workspace_id if hasattr(req_context.state, "workspace") else None
    except Exception as exc:
        logger.warning("Volume resolve: token validation failed: %s", exc)
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "TOKEN_INVALID_OR_EXPIRED",
                "message": f"Invalid token: {str(exc)}",
            },
        )

    try:
        # Look up volume by (catalog, schema, volume)
        from app.catalog.models import UnifiedCatalogVolume, UnifiedCatalogSchema, UnifiedCatalog

        schema = db.query(UnifiedCatalogSchema).join(
            UnifiedCatalog,
            UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id,
        ).filter(
            UnifiedCatalog.name == body.catalog,
            UnifiedCatalogSchema.name == body.schema_name,
        ).first()

        if not schema:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "VOLUME_NOT_FOUND",
                    "message": f"Schema '{body.catalog}.{body.schema_name}' not found",
                },
            )

        volume = db.query(UnifiedCatalogVolume).filter(
            UnifiedCatalogVolume.schema_id == schema.id,
            UnifiedCatalogVolume.name == body.volume,
        ).first()

        if not volume:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "VOLUME_NOT_FOUND",
                    "message": f"Volume '{body.catalog}.{body.schema_name}.{body.volume}' not found",
                },
            )

        # Check privilege: user must have appropriate access for requested mode
        from app.catalog.models import CatalogWorkspaceBinding
        from app.catalog.schemas import CatalogPrivilege

        # Validate mode
        if not hasattr(body, "mode") or body.mode is None:
            body_mode = "read"
        else:
            body_mode = body.mode

        if body_mode not in ("read", "write", "readwrite"):
            return JSONResponse(
                status_code=400,
                content={
                    "error_code": "INVALID_MODE",
                    "message": f"Invalid mode: {body_mode}. Must be 'read', 'write', or 'readwrite'.",
                },
            )

        if workspace_id:
            binding = db.query(CatalogWorkspaceBinding).filter(
                CatalogWorkspaceBinding.catalog_id == schema.catalog_id,
                CatalogWorkspaceBinding.workspace_id == workspace_id,
            ).first()

            if not binding:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error_code": "PERMISSION_DENIED",
                        "message": f"No access to '{body.catalog}.{body.schema_name}'",
                    },
                )

            # Check privilege based on mode
            if body_mode in ("write", "readwrite"):
                if binding.privilege != CatalogPrivilege.READ_WRITE:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error_code": "PERMISSION_DENIED",
                            "message": f"Insufficient privilege for WRITE access to '{body.catalog}.{body.schema_name}'. Required: WRITE.",
                        },
                    )
            elif body_mode == "read":
                if binding.privilege not in [CatalogPrivilege.READ_ONLY, CatalogPrivilege.READ_WRITE]:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error_code": "PERMISSION_DENIED",
                            "message": f"Insufficient privilege for READ access to '{body.catalog}.{body.schema_name}'. Required: READ.",
                        },
                    )

        # Get storage backend for volume
        storage_ctx = resolve_catalog_storage(db, body.catalog, body.schema_name)
        if not storage_ctx:
            logger.error("Volume resolve: storage context not found for schema %s", schema.id)
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "CREDENTIAL_MINT_FAILED",
                    "message": "Storage backend not configured for schema",
                },
            )

        backend = storage_ctx.backend

        # Compute scoped prefix
        container_name = backend.container
        backend_base = (storage_ctx.backend_base or "").strip("/")
        
        volume_loc = (volume.storage_location or "").strip("/")
        if volume_loc:
            if volume_loc.startswith(container_name + "/"):
                volume_prefix = volume_loc
            else:
                volume_prefix = f"{container_name}/{volume_loc}"
        else:
            if backend_base:
                volume_prefix = f"{container_name}/{backend_base}/{schema.catalog.name}/{schema.name}/volumes/{volume.name}"
            else:
                volume_prefix = f"{container_name}/{schema.catalog.name}/{schema.name}/volumes/{volume.name}"

        # Mint scoped credential
        try:
            credential_resp = await backend.mint_scoped_credential(
                prefix=volume_prefix,
                mode=body_mode,
                ttl_seconds=900,  # 15 minutes
            )
            # Add mode to response
            credential_resp["mode"] = body_mode
            logger.info(
                "Volume resolve: success for %s.%s.%s mode=%s user_id=%s",
                body.catalog, body.schema_name, body.volume, body_mode, user_id,
            )
            return credential_resp
        except Exception as exc:
            logger.error("Volume resolve: credential mint failed: %s", exc)
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "CREDENTIAL_MINT_FAILED",
                    "message": f"Failed to mint credentials: {str(exc)}",
                },
            )

    except Exception as exc:
        logger.exception("Volume resolve: unexpected error")
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "CREDENTIAL_MINT_FAILED",
                "message": f"Internal error: {str(exc)}",
            },
        )


from app.database import get_system_db, get_account_db
from app.sql_warehouse.schemas import NotebookQueryRequest
from app.sql_warehouse.query.parser import extract_table_references
from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.warehouse.manager import get_warehouse_by_id, list_warehouses
from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI

@router.post("/query")
async def run_notebook_query(
    request: Request,
    req: NotebookQueryRequest,
    db: Session = Depends(get_system_db),
    data_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
    user=Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    tables = extract_table_references(req.query)
    
    engines = set()
    catalog_api = CatalogMetadataAPI(account_db, workspace_id)
    for table_ref in tables:
        parts = table_ref.split('.')
        catalog_name = parts[0] if len(parts) > 2 else "default"
        catalog = catalog_api._catalog(catalog_name)
        if catalog:
            if catalog.catalog_type == "postgres_native":
                engines.add("postgres")
            else:
                engines.add("duckdb")
        else:
            engines.add("duckdb")

    if len(engines) > 1:
        raise HTTPException(400, "Cross-engine queries are not supported in v1")
    
    engine = list(engines)[0] if engines else "duckdb"
    
    warehouse = None
    if req.warehouse:
        warehouse = get_warehouse_by_id(db, req.warehouse, workspace_id=workspace_id)
        if not warehouse:
            warehouses = list_warehouses(db, workspace_id=workspace_id)
            for w in warehouses:
                if w.name == req.warehouse:
                    warehouse = w
                    break
        if not warehouse:
            raise HTTPException(404, f"Warehouse {req.warehouse} not found")
    else:
        warehouses = list_warehouses(db, workspace_id=workspace_id)
        for w in warehouses:
            if w.engine == engine and w.status == "running":
                warehouse = w
                break
        if not warehouse:
            for w in warehouses:
                if w.engine == engine:
                    warehouse = w
                    break
        if not warehouse:
            raise HTTPException(400, f"No warehouse available for engine {engine}")
            
    if warehouse.status != "running":
        raise HTTPException(400, f"Warehouse is {warehouse.status}, not running")

    try:
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        result = await QueryExecutor(db, data_db).run(
            warehouse=warehouse,
            sql=req.query,
            user_id=user_id,
            session_id=None,
            max_rows=10000,
        )
        if result and "columns" in result:
            result["columns"] = [{"name": c} for c in result["columns"]]
        return result
    except Exception as exc:
        raise HTTPException(400, {"error": "Query execution failed", "detail": str(exc)}) from exc
