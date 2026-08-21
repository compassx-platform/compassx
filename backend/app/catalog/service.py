from __future__ import annotations

import json
from typing import Any

import httpx
import psycopg2
import psycopg2.extras
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.catalog.models import (
    CatalogTableType,
    UnifiedCatalog,
    UnifiedCatalogColumn,
    UnifiedCatalogLineage,
    UnifiedCatalogSchema,
    UnifiedCatalogTable,
    UnifiedCatalogNotebook,
    UnifiedCatalogDashboard,
    UnifiedCatalogQuery,
    UnifiedCatalogQueryVersion,
)
from app.models.agents import DBConnection
from app.catalog.schemas import (
    CatalogColumnRead,
    CatalogSchemaSummary,
    CatalogSummary,
    CatalogTableRead,
    LineageEdgeCreate,
    LineageEdgeRead,
    LineageGraphRead,
    RemoteDatabaseRead,
    RemoteSchemaRead,
    RemoteTableRead,
    SampleDataRead,
    SchemaCreate,
    TableCreate,
    DashboardCreate,
    DashboardRead,
    DashboardUpdate,
    DashboardMove,
    VolumeCreate,
    NotebookCreate,
    NotebookUpdate,
    NotebookMove,
    QueryCreate,
    QueryRead,
    QueryUpdate,
    QueryMove,
    QueryVersionRead,
    QueryCreateVersion,
)
from app.services.encryption import decrypt_field, encrypt_field
from app.catalog.storage_context import resolve_catalog_storage, resolve_catalog_storage_by_schema_id


def _current_actor(user: dict | None) -> str:
    if not user:
        return "system"
    return str(user.get("email") or user.get("sub") or user.get("id") or "system")


def ensure_default_catalog(db: Session, created_by: str = "system") -> UnifiedCatalog:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == "compassx").first()
    if catalog:
        return catalog
    catalog = UnifiedCatalog(name="compassx", description="Default CompassX catalog", created_by=created_by)
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def list_catalogs(db: Session, workspace_id: str | None = None) -> list[CatalogSummary]:
    ensure_default_catalog(db)
    query = (
        db.query(UnifiedCatalog)
        .options(joinedload(UnifiedCatalog.schemas).joinedload(UnifiedCatalogSchema.tables))
        .order_by(UnifiedCatalog.name)
    )
    if workspace_id:
        from app.catalog.models import CatalogWorkspaceBinding
        query = query.outerjoin(CatalogWorkspaceBinding).filter(
            (UnifiedCatalog.all_workspaces == True) |
            (CatalogWorkspaceBinding.workspace_id == workspace_id)
        )
    catalogs = query.all()
    result: list[CatalogSummary] = []
    for catalog in catalogs:
        if catalog.catalog_type == "postgres" and catalog.connection_id and catalog.database_name:
            try:
                # Query schemas from the connection dynamically
                remote_schemas = browse_connection_schemas(db, catalog.connection_id, catalog.database_name)
                schema_summaries = [
                    CatalogSchemaSummary(
                        id=f"dynamic-{catalog.name}-{sch.name}",
                        name=sch.name,
                        description=f"Remote Postgres Schema: {sch.name}",
                        table_count=0,
                    )
                    for sch in remote_schemas
                ]
                result.append(
                    CatalogSummary(
                        id=catalog.id,
                        name=catalog.name,
                        description=catalog.description,
                        catalog_type=catalog.catalog_type,
                        connection_id=catalog.connection_id,
                        database_name=catalog.database_name,
                        schema_count=len(schema_summaries),
                        table_count=0,
                        schemas=schema_summaries,
                    )
                )
                continue
            except Exception as e:
                # Fallback in case of connection issues
                print(f"Error browsing dynamic schemas: {e}")

        schemas = sorted(catalog.schemas, key=lambda item: item.name.lower())
        result.append(
            CatalogSummary(
                id=catalog.id,
                name=catalog.name,
                description=catalog.description,
                catalog_type=catalog.catalog_type,
                connection_id=catalog.connection_id,
                database_name=catalog.database_name,
                schema_count=len(schemas),
                table_count=sum(len(schema.tables) for schema in schemas),
                schemas=[
                    CatalogSchemaSummary(
                        id=schema.id,
                        name=schema.name,
                        description=schema.description,
                        table_count=len(schema.tables),
                    )
                    for schema in schemas
                ],
            )
        )
    return result


def create_catalog(db: Session, body: CatalogCreate, user: dict) -> UnifiedCatalog:
    existing = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.name).first()
    if existing:
        raise ValueError(f"Catalog with name '{body.name}' already exists.")
    actor = user.get("email", "system")
    catalog = UnifiedCatalog(
        name=body.name,
        description=body.description,
        catalog_type=body.catalog_type,
        connection_id=body.connection_id,
        database_name=body.database_name,
        storage_backend_id=body.storage_backend_id,
        base_path=body.base_path,
        created_by=actor,
    )
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def create_schema(db: Session, catalog_name: str, body: SchemaCreate, user: dict) -> UnifiedCatalogSchema:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    
    existing = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == body.name)
        .first()
    )
    if existing:
        raise ValueError(f"Schema with name '{body.name}' already exists in catalog '{catalog_name}'.")
        
    actor = _current_actor(user)
    schema = UnifiedCatalogSchema(
        catalog_id=catalog.id,
        name=body.name,
        description=body.description,
        created_by=actor
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return schema


def create_table(db: Session, catalog_name: str, schema_name: str, body: TableCreate, user: dict) -> UnifiedCatalogTable:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    
    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    existing = (
        db.query(UnifiedCatalogTable)
        .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == body.name)
        .first()
    )
    if existing:
        raise ValueError(f"Table '{body.name}' already exists in schema '{schema_name}'.")

    actor = _current_actor(user)
    table = UnifiedCatalogTable(
        schema_id=schema.id,
        name=body.name,
        description=body.description,
        table_type=body.table_type,
        owner=actor,
        created_by=actor
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    # Enqueue embedding for semantic search
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        col_summary = None
        enqueue_asset_for_embedding(
            db,
            object_type="table",
            source_object_id=table.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=table.name,
            description=table.description,
            content_summary=col_summary,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for table %s: %s", table.name, _idx_err)

    return table


async def create_volume(db: Session, catalog_name: str, schema_name: str, body: VolumeCreate, user: dict):
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    
    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    ctx = resolve_catalog_storage(db, catalog_name, schema_name)
    if not ctx:
        raise ValueError(
            f"No storage backend configured for schema '{schema_name}' or its parent catalog '{catalog_name}'. "
            "Bind a blob storage backend to the catalog or schema first."
        )

    from app.catalog.models import UnifiedCatalogVolume
    existing = (
        db.query(UnifiedCatalogVolume)
        .filter(UnifiedCatalogVolume.schema_id == schema.id, UnifiedCatalogVolume.name == body.name)
        .first()
    )
    if existing:
        raise ValueError(f"Volume '{body.name}' already exists in schema '{schema_name}'.")

    actor = _current_actor(user)
    storage_loc = ctx.abs_path(f"volumes/{body.name}/")
    rel_path = ctx.rel_path(f"volumes/{body.name}/.keep")
    await ctx.backend.write_bytes(rel_path, b"", "application/octet-stream")

    volume = UnifiedCatalogVolume(
        schema_id=schema.id,
        name=body.name,
        description=body.description,
        storage_location=storage_loc,
        owner=actor,
        created_by=actor
    )
    db.add(volume)
    db.commit()
    db.refresh(volume)

    # Enqueue embedding for semantic search
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="volume",
            source_object_id=volume.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=volume.name,
            description=volume.description,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for volume %s: %s", volume.name, _idx_err)

    return volume


def list_volumes(db: Session, catalog: str | None = None, schema_name: str | None = None) -> list[UnifiedCatalogVolume]:
    from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogVolume
    query = db.query(UnifiedCatalogVolume)
    
    if catalog or schema_name:
        query = query.join(UnifiedCatalogVolume.schema).join(UnifiedCatalogSchema.catalog)
        if catalog:
            query = query.filter(UnifiedCatalog.name == catalog)
        if schema_name:
            query = query.filter(UnifiedCatalogSchema.name == schema_name)
            
    return query.order_by(UnifiedCatalogVolume.name).all()


async def create_iceberg_schema(
    db: Session,
    catalog_name: str,
    schema_name: str,
    storage_backend_name: str,
    user: dict,
    description: str | None = None,
) -> dict:
    """
    Create an Iceberg schema:
    1. Resolves the storage backend and computes a base_path.
    2. Upserts the schema row in Postgres with storage_backend_id + base_path.
    3. Writes a .schema marker file to blob storage.
    """
    from app.storage.db_models import StorageBackend
    from app.storage.service import storage_service
    from app.catalog.iceberg_manager import IcebergManager
    from app.catalog.storage_context import _get_backend_base

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found")

    backend_row = db.query(StorageBackend).filter(StorageBackend.name == storage_backend_name).first()
    if not backend_row:
        raise ValueError(f"Storage backend '{storage_backend_name}' not found")

    backend_base = _get_backend_base(backend_row)

    # base_path stored in DB = absolute from container root (used by DuckDB)
    base_path = f"{backend_base}{catalog_name}/{schema_name}/"
    # relative path passed to IcebergManager (it will prepend backend.base_path internally)
    iceberg_relative = f"{catalog_name}/{schema_name}"

    actor = _current_actor(user)
    existing = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if existing:
        existing.storage_backend_id = backend_row.id
        existing.base_path = base_path
        if description:
            existing.description = description
        schema = existing
    else:
        schema = UnifiedCatalogSchema(
            catalog_id=catalog.id,
            name=schema_name,
            description=description,
            storage_backend_id=backend_row.id,
            base_path=base_path,
            created_by=actor,
        )
        db.add(schema)

    db.commit()

    backend = storage_service.get_backend(db, storage_backend_name)
    # Pass relative path — backend prepends its own base_path internally
    try:
        await IcebergManager(backend).create_schema(iceberg_relative)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to write Iceberg schema marker to blob storage: %s", e)

    return {
        "catalog": catalog_name,
        "schema": schema_name,
        "base_path": base_path,
        "storage_backend": storage_backend_name,
    }


async def create_iceberg_table(
    db: Session,
    catalog_name: str,
    schema_name: str,
    table_name: str,
    columns: list[dict],
    user: dict,
    description: str | None = None,
    properties: dict | None = None,
) -> UnifiedCatalogTable:
    """
    Create an Iceberg table:
    1. Resolves the schema's storage backend.
    2. Writes Iceberg v2 metadata JSON to blob storage.
    3. Creates the table row in Postgres with metadata_location set.
    """
    from app.catalog.iceberg_manager import IcebergManager

    if properties is None:
        properties = {}

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found")

    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if not schema:
        raise ValueError(f"Schema '{catalog_name}.{schema_name}' not found")

    ctx = resolve_catalog_storage(db, catalog_name, schema_name)
    if not ctx:
        raise ValueError(
            f"No storage backend configured for schema '{schema_name}' or its parent catalog '{catalog_name}'. "
            "Use POST /iceberg/schemas to configure storage first."
        )

    table_path_abs = ctx.abs_path(f"tables/{table_name}")
    table_path_rel = ctx.rel_path(f"tables/{table_name}")

    mgr = IcebergManager(ctx.backend)

    if await mgr.table_exists(table_path_rel):
        raise ValueError(
            f"Iceberg metadata already exists at {table_path_abs}. "
            "The table name is already in use on blob storage."
        )

    metadata_location_rel = await mgr.create_table(
        table_path=table_path_rel,
        table_name=table_name,
        columns=columns,
        properties=properties,
    )
    # Convert relative metadata location back to absolute for DB storage
    metadata_location_abs = f"{ctx.backend_base}{metadata_location_rel}"

    actor = _current_actor(user)
    existing = (
        db.query(UnifiedCatalogTable)
        .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == table_name)
        .first()
    )
    if existing:
        raise ValueError(f"Table '{table_name}' already exists in schema '{schema_name}'")

    table = UnifiedCatalogTable(
        schema_id=schema.id,
        name=table_name,
        table_type=CatalogTableType.ICEBERG,
        metadata_location=metadata_location_abs,
        storage_location=table_path_abs,
        description=description,
        owner=actor,
        created_by=actor,
        properties=properties,
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    # Enqueue embedding for semantic search (column summary built from columns list)
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        col_summary = ", ".join(
            f"{c['name']} ({c.get('type', '')})".strip() for c in columns
        ) if columns else None
        enqueue_asset_for_embedding(
            db,
            object_type="table",
            source_object_id=table.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=table_name,
            description=description,
            content_summary=col_summary,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for iceberg table %s: %s", table_name, _idx_err)

    return table


def delete_catalog(db: Session, catalog_name: str) -> None:
    """Delete a catalog by name.

    For Postgres catalogs only the catalog row itself is removed —
    the underlying database schemas and tables are not touched.
    For Iceberg/default catalogs all child UnifiedCatalogSchema and
    UnifiedCatalogTable rows are cascade-deleted by the ORM.
    """
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    db.delete(catalog)
    db.commit()


def list_tables(db: Session, catalog: str | None = None, schema_name: str | None = None) -> list[CatalogTableRead]:
    if catalog:
        cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog).first()
        if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
            if not schema_name:
                return []
            try:
                # Query remote tables dynamically
                remote_tables = browse_connection_tables(db, cat_model.connection_id, cat_model.database_name, schema_name)
                result = []
                for tbl in remote_tables:
                    fqn = f"{catalog}.{schema_name}.{tbl.name}"
                    result.append(
                        CatalogTableRead(
                            id=fqn,
                            fqn=fqn,
                            catalog=catalog,
                            schema_name=schema_name,
                            name=tbl.name,
                            table_type=CatalogTableType.POSTGRES_NATIVE,
                            description=f"Dynamically loaded Postgres Table: {tbl.name}",
                            owner="postgres-owner",
                            read_roles=[],
                            write_roles=[],
                            properties={},
                            created_at=cat_model.created_at,
                            updated_at=cat_model.created_at,
                            connection_id=cat_model.connection_id,
                            connection_name=cat_model.connection.name if cat_model.connection else None,
                            source_database=cat_model.database_name,
                            pg_schema=schema_name,
                            pg_table=tbl.name,
                            columns=[]
                        )
                    )
                return result
            except Exception as e:
                print(f"Error listing dynamic tables: {e}")
                return []

    query = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
        .order_by(UnifiedCatalog.name, UnifiedCatalogSchema.name, UnifiedCatalogTable.name)
    )
    if catalog:
        query = query.filter(UnifiedCatalog.name == catalog)
    if schema_name:
        query = query.filter(UnifiedCatalogSchema.name == schema_name)
    return [_to_table_read(item) for item in query.all()]


def get_table(db: Session, fqn: str) -> CatalogTableRead:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()

    # For postgres catalogs: prefer stored synced rows; fall back to live introspection
    if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
        stored = (
            db.query(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
            .filter(
                UnifiedCatalogSchema.catalog_id == cat_model.id,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogTable.name == table_name,
            )
            .first()
        )
        if stored and stored.columns:
            return _to_table_read(stored)

        # Fall back to live introspection (not yet synced)
        temp_table = UnifiedCatalogTable(
            table_type=CatalogTableType.POSTGRES_NATIVE,
            connection_id=cat_model.connection_id,
            source_database=cat_model.database_name,
            pg_schema=schema_name,
            pg_table=table_name,
        )
        try:
            columns = introspect_columns(db, temp_table)
            return CatalogTableRead(
                id=fqn,
                fqn=fqn,
                catalog=catalog_name,
                schema_name=schema_name,
                name=table_name,
                table_type=CatalogTableType.POSTGRES_NATIVE,
                description=f"Dynamically loaded Postgres Table: {table_name}",
                owner="postgres-owner",
                read_roles=[],
                write_roles=[],
                properties={},
                created_at=cat_model.created_at,
                updated_at=cat_model.created_at,
                connection_id=cat_model.connection_id,
                connection_name=cat_model.connection.name if cat_model.connection else None,
                source_database=cat_model.database_name,
                pg_schema=schema_name,
                pg_table=table_name,
                columns=columns
            )
        except Exception as e:
            raise ValueError(f"Failed to introspect table {fqn}: {e}")

    table = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
        .filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name,
            UnifiedCatalogTable.name == table_name,
        )
        .first()
    )
    if not table:
        raise ValueError(f"Table '{fqn}' not found")
    return _to_table_read(table)





def browse_connection_databases(db: Session, connection_id: int) -> list[RemoteDatabaseRead]:
    record = _get_connection(db, connection_id)
    conn = _connect_record(record)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT datname AS name,
                   pg_catalog.pg_get_userbyid(datdba) AS owner
            FROM pg_catalog.pg_database
            WHERE datistemplate = false
            ORDER BY datname
            """
        )
        return [RemoteDatabaseRead(**dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def browse_connection_schemas(db: Session, connection_id: int, database: str) -> list[RemoteSchemaRead]:
    record = _get_connection(db, connection_id)
    conn = _connect_record(record, database)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT schema_name AS name,
                   schema_owner AS owner
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND schema_name NOT LIKE 'pg_temp_%'
              AND schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER BY schema_name
            """
        )
        return [RemoteSchemaRead(**dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def browse_connection_tables(db: Session, connection_id: int, database: str, schema_name: str) -> list[RemoteTableRead]:
    record = _get_connection(db, connection_id)
    conn = _connect_record(record, database)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT t.table_name AS name,
                   t.table_schema AS schema_name,
                   t.table_type,
                   s.n_live_tup::bigint AS row_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s
                   ON s.schemaname = t.table_schema
                  AND s.relname = t.table_name
            WHERE t.table_schema = %s
            ORDER BY t.table_type, t.table_name
            """,
            (schema_name,),
        )
        return [RemoteTableRead(**dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()



def refresh_columns(db: Session, fqn: str) -> CatalogTableRead:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    table = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name,
            UnifiedCatalogTable.name == table_name,
        )
        .first()
    )
    if not table:
        raise ValueError(f"Table '{fqn}' not found")
    columns = introspect_columns(db, table)
    _replace_columns(db, table, columns)
    return get_table(db, fqn)


def register_lineage(db: Session, data: LineageEdgeCreate, user: dict | None) -> None:
    actor = _current_actor(user)
    source = _get_table_model(db, data.source_fqn)
    target = _get_table_model(db, data.target_fqn)
    edge = (
        db.query(UnifiedCatalogLineage)
        .filter(
            UnifiedCatalogLineage.source_table_id == source.id,
            UnifiedCatalogLineage.target_table_id == target.id,
        )
        .first()
    )
    if edge is None:
        edge = UnifiedCatalogLineage(source_table_id=source.id, target_table_id=target.id, created_by=actor)
        db.add(edge)
    edge.transformation = data.transformation
    db.commit()


def get_lineage(db: Session, fqn: str) -> LineageGraphRead:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if cat_model and cat_model.catalog_type == "postgres":
        return LineageGraphRead(upstream=[], downstream=[])

    table = _get_table_model(db, fqn)
    upstream_rows = (
        db.query(UnifiedCatalogLineage, UnifiedCatalogTable, UnifiedCatalogSchema, UnifiedCatalog)
        .join(UnifiedCatalogTable, UnifiedCatalogLineage.source_table_id == UnifiedCatalogTable.id)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .filter(UnifiedCatalogLineage.target_table_id == table.id)
        .all()
    )
    downstream_rows = (
        db.query(UnifiedCatalogLineage, UnifiedCatalogTable, UnifiedCatalogSchema, UnifiedCatalog)
        .join(UnifiedCatalogTable, UnifiedCatalogLineage.target_table_id == UnifiedCatalogTable.id)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .filter(UnifiedCatalogLineage.source_table_id == table.id)
        .all()
    )
    return LineageGraphRead(
        upstream=[
            LineageEdgeRead(
                source_fqn=f"{catalog.name}.{schema.name}.{related.name}",
                target_fqn=fqn,
                transformation=edge.transformation,
                created_at=edge.created_at,
            )
            for edge, related, schema, catalog in upstream_rows
        ],
        downstream=[
            LineageEdgeRead(
                source_fqn=fqn,
                target_fqn=f"{catalog.name}.{schema.name}.{related.name}",
                transformation=edge.transformation,
                created_at=edge.created_at,
            )
            for edge, related, schema, catalog in downstream_rows
        ],
    )


async def get_sample_data(db: Session, fqn: str, limit: int = 100) -> SampleDataRead:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()

    # Postgres catalog — query live
    if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
        conn = _connect_record(_get_connection(db, cat_model.connection_id), cat_model.database_name)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT %s',
                (limit,),
            )
            rows_raw = cur.fetchall()
            if not rows_raw:
                return SampleDataRead(columns=[], rows=[], row_count=0)
            columns = list(rows_raw[0].keys())
            rows = [[str(v) if v is not None else None for v in row.values()] for row in rows_raw]
            return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
        finally:
            conn.close()

    # Registered table (either postgres_native or iceberg)
    table = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name,
            UnifiedCatalogTable.name == table_name,
        )
        .first()
    )
    if not table:
        raise ValueError(f"Table '{fqn}' not found")

    if table.table_type == CatalogTableType.POSTGRES_NATIVE and table.connection_id:
        conn = _connect_record(_get_connection(db, table.connection_id), table.source_database)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f'SELECT * FROM "{table.pg_schema}"."{table.pg_table}" LIMIT %s',
                (limit,),
            )
            rows_raw = cur.fetchall()
            if not rows_raw:
                return SampleDataRead(columns=[], rows=[], row_count=0)
            columns = list(rows_raw[0].keys())
            rows = [[str(v) if v is not None else None for v in row.values()] for row in rows_raw]
            return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
        finally:
            conn.close()

    if table.table_type == CatalogTableType.ICEBERG:
        sch = table.schema
        cat_name = sch.catalog.name if sch and sch.catalog else catalog_name
        ctx = resolve_catalog_storage(db, cat_name, sch.name if sch else schema_name)
        if not ctx:
            raise ValueError("No storage backend configured for this schema")

        data_file = table.properties.get("data_file")
        if not data_file:
            table_path_rel = ctx.rel_path(f"tables/{table.name}")
            files = await ctx.backend.list_files(f"{table_path_rel}/data/")
            data_files = [f for f in files if f.file_name != "_keep"]
            if data_files:
                data_file = data_files[0].file_name

        if not data_file:
            return SampleDataRead(columns=[c.name for c in table.columns], rows=[], row_count=0)

        table_path_rel = ctx.rel_path(f"tables/{table.name}")
        file_path = f"{table_path_rel}/data/{data_file}"

        try:
            file_bytes = await ctx.backend.read_bytes(file_path)
            import io
            import pandas as pd
            import numpy as np
            ext = data_file.split('.')[-1].lower()
            if ext == 'csv':
                df = pd.read_csv(io.BytesIO(file_bytes))
            elif ext in ('xls', 'xlsx'):
                df = pd.read_excel(io.BytesIO(file_bytes))
            elif ext in ('json', 'jsonl'):
                df = pd.read_json(io.BytesIO(file_bytes), lines=(ext == 'jsonl' or b'\n' in file_bytes))
            elif ext == 'parquet':
                df = pd.read_parquet(io.BytesIO(file_bytes))
            else:
                df = pd.read_csv(io.BytesIO(file_bytes))

            df_head = df.head(limit)
            columns = list(df_head.columns)
            rows = []
            for _, row in df_head.iterrows():
                row_vals = []
                for col in columns:
                    val = row.get(col)
                    if pd.isna(val) or val is None or (isinstance(val, float) and np.isnan(val)):
                        row_vals.append(None)
                    else:
                        row_vals.append(str(val))
                rows.append(row_vals)
            return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
        except Exception as e:
            print(f"Error reading sample data from Iceberg blob: {e}")
            return SampleDataRead(columns=[c.name for c in table.columns], rows=[], row_count=0)

    raise ValueError(f"Sample data not supported for table type '{table.table_type}'")



def introspect_columns(db: Session, table: UnifiedCatalogTable) -> list[CatalogColumnRead]:
    if table.table_type == CatalogTableType.POSTGRES_NATIVE:
        connection = _get_connection(db, table.connection_id)
        conn = _connect_record(connection, table.source_database)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table.pg_schema, table.pg_table),
            )
            rows = cur.fetchall()
            return [
                CatalogColumnRead(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                    ordinal=row["ordinal_position"],
                )
                for row in rows
            ]
        finally:
            conn.close()
    return _introspect_iceberg_columns(table.metadata_location)


def _introspect_iceberg_columns(metadata_location: str | None) -> list[CatalogColumnRead]:
    if not metadata_location:
        return []
    if metadata_location.startswith("http://") or metadata_location.startswith("https://"):
        with httpx.Client(timeout=10) as client:
            resp = client.get(metadata_location)
            resp.raise_for_status()
            metadata = resp.json()
    else:
        return []

    current_schema_id = metadata.get("current-schema-id", 0)
    schemas = metadata.get("schemas") or ([metadata.get("schema")] if metadata.get("schema") else [])
    current_schema = next((s for s in schemas if s and s.get("schema-id") == current_schema_id), schemas[0] if schemas else {})
    fields = current_schema.get("fields", []) if current_schema else []
    return [
        CatalogColumnRead(
            name=field["name"],
            data_type=_resolve_iceberg_type(field.get("type")),
            nullable=not field.get("required", False),
            description=field.get("doc"),
            ordinal=index + 1,
        )
        for index, field in enumerate(fields)
    ]


def _resolve_iceberg_type(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        kind = value.get("type", "unknown")
        if kind == "list":
            return f"list<{_resolve_iceberg_type(value.get('element-type', 'string'))}>"
        if kind == "map":
            return f"map<{_resolve_iceberg_type(value.get('key-type', 'string'))},{_resolve_iceberg_type(value.get('value-type', 'string'))}>"
        if kind == "decimal":
            return f"decimal({value.get('precision', 38)},{value.get('scale', 0)})"
        return kind
    return "unknown"


def _replace_columns(db: Session, table: UnifiedCatalogTable, columns: list[CatalogColumnRead]) -> None:
    db.query(UnifiedCatalogColumn).filter(UnifiedCatalogColumn.table_id == table.id).delete()
    for column in columns:
        db.add(
            UnifiedCatalogColumn(
                table_id=table.id,
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                description=column.description,
                ordinal=column.ordinal,
                properties=column.properties,
            )
        )
    db.commit()


def _to_table_read(table: UnifiedCatalogTable) -> CatalogTableRead:
    catalog = table.schema.catalog
    fqn = f"{catalog.name}.{table.schema.name}.{table.name}"
    return CatalogTableRead(
        id=table.id,
        fqn=fqn,
        catalog=catalog.name,
        schema_name=table.schema.name,
        name=table.name,
        table_type=table.table_type,
        description=table.description,
        owner=table.owner,
        read_roles=list(table.read_roles or []),
        write_roles=list(table.write_roles or []),
        properties=dict(table.properties or {}),
        created_at=table.created_at,
        updated_at=table.updated_at,
        connection_id=table.connection_id,
        connection_name=table.connection.name if table.connection else None,
        source_database=table.source_database,
        pg_schema=table.pg_schema,
        pg_table=table.pg_table,
        metadata_location=table.metadata_location,
        storage_location=table.storage_location,
        columns=[
            CatalogColumnRead(
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                description=column.description,
                ordinal=column.ordinal,
                properties=dict(column.properties or {}),
            )
            for column in sorted(table.columns, key=lambda item: item.ordinal)
        ],
    )


def _parse_fqn(fqn: str) -> tuple[str, str, str]:
    parts = fqn.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected catalog.schema.table, got '{fqn}'")
    return parts[0], parts[1], parts[2]


def _get_connection(db: Session, connection_id: int | None) -> DBConnection:
    if not connection_id:
        raise ValueError("Connection not found")
    from app.database import AccountSessionLocal
    sys_db = AccountSessionLocal()
    try:
        record = sys_db.query(DBConnection).filter(DBConnection.id == connection_id).first()
        if not record:
            raise ValueError("Connection not found")
        sys_db.expunge(record)
        return record
    finally:
        sys_db.close()


def _get_table_model(db: Session, fqn: str) -> UnifiedCatalogTable:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    row = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .options(joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
        .filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name,
            UnifiedCatalogTable.name == table_name,
        )
        .first()
    )
    if not row:
        raise ValueError(f"Table '{fqn}' not found")
    return row


def _ensure_catalog_by_name(db: Session, name: str, actor: str) -> UnifiedCatalog:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == name).first()
    if catalog:
        return catalog
    catalog = UnifiedCatalog(name=name, created_by=actor)
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def _ensure_schema_by_name(db: Session, catalog: UnifiedCatalog, name: str, actor: str) -> UnifiedCatalogSchema:
    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == name)
        .first()
    )
    if schema:
        return schema
    schema = UnifiedCatalogSchema(catalog_id=catalog.id, name=name, created_by=actor)
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return schema


def _connect_record(record: DBConnection, database: str | None = None):
    ssl_mode = "require" if (record.ssl_config and record.ssl_config.get("ssl_required")) else "prefer"
    return _connect_raw(
        host=record.host or "localhost",
        port=record.port or 5432,
        database=database or record.db_name or "postgres",
        username=decrypt_field(record.username_enc) if record.username_enc else "",
        password=decrypt_field(record.password_enc) if record.password_enc else "",
        ssl_mode=ssl_mode,
    )


def _connect_raw(*, host: str, port: int, database: str, username: str, password: str, ssl_mode: str):
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=username,
        password=password,
        sslmode=ssl_mode,
        connect_timeout=10,
        options="-c statement_timeout=30000",
    )


async def create_table_from_file(
    db: Session,
    catalog_name: str,
    schema_name: str,
    table_name: str,
    description: str | None,
    columns: list[dict],
    file_name: str,
    file_bytes: bytes,
    user: dict,
) -> UnifiedCatalogTable:
    import io
    import pandas as pd
    import numpy as np

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")

    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
        .first()
    )
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    existing = (
        db.query(UnifiedCatalogTable)
        .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == table_name)
        .first()
    )
    if existing:
        raise ValueError(f"Table '{table_name}' already exists in schema '{schema_name}'.")

    ext = file_name.split('.')[-1].lower() if file_name else 'csv'
    try:
        if ext == 'csv':
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif ext in ('xls', 'xlsx'):
            df = pd.read_excel(io.BytesIO(file_bytes))
        elif ext in ('json', 'jsonl'):
            df = pd.read_json(io.BytesIO(file_bytes), lines=(ext == 'jsonl' or b'\n' in file_bytes))
        elif ext == 'parquet':
            df = pd.read_parquet(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Failed to parse uploaded file: {e}")

    actor = _current_actor(user)

    if catalog.catalog_type == "postgres" and catalog.connection_id:
        # 1. CREATE TABLE in PostgreSQL database
        connection = _get_connection(db, catalog.connection_id)

        cols_sql = []
        for c in columns:
            col_name = c["name"]
            dt = c.get("data_type", "string").lower()
            null_str = "NULL" if c.get("nullable", True) else "NOT NULL"

            if dt in ("int", "int32", "integer"):
                pg_type = "INTEGER"
            elif dt in ("long", "int64", "bigint"):
                pg_type = "BIGINT"
            elif dt in ("double", "float64", "float", "real"):
                pg_type = "DOUBLE PRECISION"
            elif dt in ("bool", "boolean"):
                pg_type = "BOOLEAN"
            elif dt in ("timestamp", "timestamptz", "datetime"):
                pg_type = "TIMESTAMP WITH TIME ZONE"
            elif dt == "date":
                pg_type = "DATE"
            elif dt == "decimal":
                pg_type = "NUMERIC"
            elif dt == "json":
                pg_type = "JSONB"
            elif dt == "binary":
                pg_type = "BYTEA"
            else:
                pg_type = "TEXT"

            cols_sql.append(f'"{col_name}" {pg_type} {null_str}')

        create_sql = f'CREATE TABLE "{schema_name}"."{table_name}" (\n  ' + ",\n  ".join(cols_sql) + "\n)"

        conn = _connect_record(connection, catalog.database_name)
        try:
            cur = conn.cursor()
            cur.execute(create_sql)

            # Insert values
            placeholders = ", ".join(["%s"] * len(columns))
            col_names_str = ", ".join([f'"{c["name"]}"' for c in columns])
            insert_sql = f'INSERT INTO "{schema_name}"."{table_name}" ({col_names_str}) VALUES ({placeholders})'

            rows_to_insert = []
            for _, row in df.iterrows():
                row_vals = []
                for col_info in columns:
                    name = col_info["name"]
                    val = row.get(name)
                    if pd.isna(val) or val is None or (isinstance(val, float) and np.isnan(val)):
                        row_vals.append(None)
                    else:
                        dt = col_info.get("data_type", "string").lower()
                        if dt in ("int", "int32", "integer", "long", "int64", "bigint"):
                            try:
                                row_vals.append(int(val))
                            except:
                                row_vals.append(None)
                        elif dt in ("double", "float64", "float", "real", "decimal"):
                            try:
                                row_vals.append(float(val))
                            except:
                                row_vals.append(None)
                        elif dt in ("bool", "boolean"):
                            if isinstance(val, str):
                                row_vals.append(val.lower() in ("true", "1", "yes", "t"))
                            else:
                                row_vals.append(bool(val))
                        else:
                            row_vals.append(str(val))
                rows_to_insert.append(row_vals)

            if rows_to_insert:
                cur.executemany(insert_sql, rows_to_insert)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Postgres storage failed: {e}")
        finally:
            conn.close()

        # 2. Register in metadata
        table = UnifiedCatalogTable(
            schema_id=schema.id,
            name=table_name,
            table_type=CatalogTableType.POSTGRES_NATIVE,
            connection_id=catalog.connection_id,
            source_database=catalog.database_name,
            pg_schema=schema_name,
            pg_table=table_name,
            description=description,
            owner=actor,
            created_by=actor
        )
        db.add(table)
        db.commit()
        db.refresh(table)

    elif catalog.catalog_type in ("iceberg", None, ""):
        # ── Iceberg storage: always write Parquet, never raw CSV/JSON ─────────
        from app.catalog.iceberg_manager import IcebergManager

        ctx_upload = resolve_catalog_storage(db, catalog_name, schema_name)
        if not ctx_upload:
            raise ValueError(
                f"No storage backend configured for schema '{schema_name}' or catalog '{catalog_name}'. "
                "Bind a blob storage backend to the catalog or schema first."
            )

        table_path_abs = ctx_upload.abs_path(f"tables/{table_name}")
        table_path_rel = ctx_upload.rel_path(f"tables/{table_name}")

        mgr = IcebergManager(ctx_upload.backend)

        if await mgr.table_exists(table_path_rel):
            raise ValueError(
                f"Iceberg metadata already exists at {table_path_abs}. "
                "The table name is already in use on blob storage."
            )

        # ── Convert data to Parquet (native Iceberg storage format) ──────────
        # Apply user-specified column types before writing
        import io as _io
        for col_info in columns:
            col_name = col_info["name"]
            dt = col_info.get("data_type", "string").lower()
            if col_name not in df.columns:
                continue
            try:
                if dt in ("int", "int32", "integer"):
                    df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("Int32")
                elif dt in ("long", "int64", "bigint"):
                    df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("Int64")
                elif dt in ("double", "float64", "float", "real", "decimal"):
                    df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("float64")
                elif dt in ("bool", "boolean"):
                    df[col_name] = df[col_name].map(
                        lambda v: True if str(v).lower() in ("true", "1", "yes", "t") else False
                        if str(v).lower() in ("false", "0", "no", "f") else None
                    )
                elif dt == "timestamp":
                    df[col_name] = pd.to_datetime(df[col_name], errors="coerce", utc=True)
                elif dt == "date":
                    df[col_name] = pd.to_datetime(df[col_name], errors="coerce").dt.date
            except Exception:
                pass  # Keep column as-is if cast fails

        parquet_buf = _io.BytesIO()
        df.to_parquet(parquet_buf, index=False, engine="pyarrow")
        parquet_bytes = parquet_buf.getvalue()
        parquet_file_name = f"{table_name}.parquet"
        storage_format = "parquet"
        # ─────────────────────────────────────────────────────────────────────

        # Write Parquet file to the storage backend under data/
        await ctx_upload.backend.write_bytes(
            path=f"{table_path_rel}/data/{parquet_file_name}",
            data=parquet_bytes,
            content_type="application/octet-stream"
        )

        metadata_location_rel = await mgr.create_table(
            table_path=table_path_rel,
            table_name=table_name,
            columns=columns,
            properties={"file_format": storage_format, "data_file": parquet_file_name}
        )
        metadata_location_abs = f"{ctx_upload.backend_base}{metadata_location_rel}"

        table = UnifiedCatalogTable(
            schema_id=schema.id,
            name=table_name,
            table_type=CatalogTableType.ICEBERG,
            metadata_location=metadata_location_abs,
            storage_location=table_path_abs,
            file_format=storage_format,
            description=description,
            owner=actor,
            created_by=actor,
            properties={"data_file": parquet_file_name, "file_format": storage_format, "source_file": file_name}
        )
        db.add(table)
        db.commit()
        db.refresh(table)

    else:
        raise ValueError(
            f"Unsupported catalog type '{catalog.catalog_type}'. "
            "File-based table creation is supported for 'postgres' and 'iceberg' catalog types only."
        )

    # Common: Register columns
    for idx, col in enumerate(columns):
        db.add(
            UnifiedCatalogColumn(
                table_id=table.id,
                name=col["name"],
                data_type=col.get("data_type", "string"),
                nullable=col.get("nullable", True),
                description=col.get("description"),
                ordinal=idx + 1
            )
        )
    db.commit()
    db.refresh(table)

    # Enqueue embedding for semantic search
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        col_summary = ", ".join(f"{c['name']} ({c.get('data_type', 'string')})" for c in columns)
        enqueue_asset_for_embedding(
            db,
            object_type="table",
            source_object_id=table.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=table.name,
            description=table.description,
            content_summary=col_summary,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for table %s: %s", table.name, _idx_err)

    return table


def list_notebooks(db: Session, catalog_name: str, schema_name: str) -> list[UnifiedCatalogNotebook]:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")
    return db.query(UnifiedCatalogNotebook).filter(UnifiedCatalogNotebook.schema_id == schema.id).order_by(UnifiedCatalogNotebook.name).all()


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.new_event_loop().run_until_complete(coro))
            return future.result()
    else:
        return loop.run_until_complete(coro)


def _resolve_notebook_ctx(db: Session, schema) -> "StorageContext | None":
    """Resolve StorageContext for a notebook's schema, walking up to catalog if needed."""
    return resolve_catalog_storage_by_schema_id(db, schema.id)


async def _write_notebook_content(db: Session, schema, blob_path: str, content: dict) -> None:
    import json
    ctx = _resolve_notebook_ctx(db, schema)
    content_str = json.dumps(content, indent=2)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        await ctx.backend.write_bytes(key, content_str.encode("utf-8"), "application/x-ipynb+json")
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        fs.write_text(_NOTEBOOKS_BUCKET, key, content_str)


async def _read_notebook_content(db: Session, schema, blob_path: str) -> dict:
    import json
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        data = await ctx.backend.read_bytes(key)
        return json.loads(data.decode("utf-8"))
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        return json.loads(fs.read_text(_NOTEBOOKS_BUCKET, key))


async def _delete_notebook_file(db: Session, schema, blob_path: str) -> None:
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        try:
            if await ctx.backend.exists(key):
                await ctx.backend.delete(key)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to delete storage notebook key %s: %s", key, e)
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        try:
            if fs.exists(_NOTEBOOKS_BUCKET, key):
                fs.delete(_NOTEBOOKS_BUCKET, key)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to delete notebook key %s: %s", key, e)


async def _notebook_exists(db: Session, schema, blob_path: str) -> bool:
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        return await ctx.backend.exists(key)
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        return fs.exists(_NOTEBOOKS_BUCKET, key)


def get_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str) -> UnifiedCatalogNotebook:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")
    notebook = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.schema_id == schema.id,
        UnifiedCatalogNotebook.name == notebook_name
    ).first()
    if not notebook:
        raise ValueError(f"Notebook '{notebook_name}' not found in schema '{catalog_name}.{schema_name}'.")
    return notebook


async def create_notebook(db: Session, catalog_name: str, schema_name: str, body: NotebookCreate, user: dict) -> UnifiedCatalogNotebook:
    from uuid import uuid4

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    # Check for name namespace conflict
    existing = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.catalog_name == catalog_name,
        UnifiedCatalogNotebook.schema_name == schema_name,
        UnifiedCatalogNotebook.name == body.name
    ).first()
    if existing:
        raise ValueError(f"Notebook '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

    # Write empty skeleton to storage
    nb_id = str(uuid4())
    rel_path = f"{nb_id}.ipynb"

    empty_nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "cells": [],
    }
    content = body.initial_content if body.initial_content else empty_nb
    
    await _write_notebook_content(db, schema, rel_path, content)

    actor = _current_actor(user)
    notebook = UnifiedCatalogNotebook(
        schema_id=schema.id,
        catalog_name=catalog_name,
        schema_name=schema_name,
        name=body.name,
        blob_path=rel_path,
        owner=actor,
        comment=body.comment,
        created_by=actor,
        updated_by=actor,
    )
    db.add(notebook)
    db.commit()
    db.refresh(notebook)

    # Enqueue embedding for semantic search
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="notebook",
            source_object_id=notebook.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=notebook.name,
            description=notebook.comment,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for notebook %s: %s", notebook.name, _idx_err)

    return notebook


def update_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookUpdate, user: dict) -> UnifiedCatalogNotebook:
    notebook = get_notebook(db, catalog_name, schema_name, notebook_name)
    
    actor = _current_actor(user)
    if body.comment is not None:
        notebook.comment = body.comment
    if body.owner is not None:
        notebook.owner = body.owner
    if body.name is not None and body.name != notebook.name:
        # Check name uniqueness in target schema
        existing = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.catalog_name == catalog_name,
            UnifiedCatalogNotebook.schema_name == schema_name,
            UnifiedCatalogNotebook.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Notebook '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
        notebook.name = body.name

    notebook.updated_by = actor
    db.commit()
    db.refresh(notebook)

    # Re-enqueue embedding whenever name or comment changes (metadata fields per spec §4)
    if body.name is not None or body.comment is not None:
        try:
            from app.catalog.search_indexer import enqueue_asset_for_embedding
            enqueue_asset_for_embedding(
                db,
                object_type="notebook",
                source_object_id=notebook.id,
                catalog_name=notebook.catalog_name,
                schema_name=notebook.schema_name,
                object_name=notebook.name,
                description=notebook.comment,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            _log.getLogger(__name__).warning("Failed to re-enqueue embedding for notebook %s: %s", notebook.name, _idx_err)

    return notebook


async def move_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookMove, user: dict) -> UnifiedCatalogNotebook:
    notebook = get_notebook(db, catalog_name, schema_name, notebook_name)
    
    target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
    if not target_catalog:
        raise ValueError(f"Target catalog '{body.target_catalog}' not found.")
    
    target_schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == target_catalog.id,
        UnifiedCatalogSchema.name == body.target_schema
    ).first()
    if not target_schema:
        raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

    dest_name = body.new_name if body.new_name else notebook.name
    
    # Check for name uniqueness in target schema
    existing = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.catalog_name == body.target_catalog,
        UnifiedCatalogNotebook.schema_name == body.target_schema,
        UnifiedCatalogNotebook.name == dest_name
    ).first()
    if existing:
        raise ValueError(f"Notebook '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

    old_schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
    if old_schema and old_schema.id != target_schema.id:
        try:
            content = await _read_notebook_content(db, old_schema, notebook.blob_path)
            await _write_notebook_content(db, target_schema, notebook.blob_path, content)
            await _delete_notebook_file(db, old_schema, notebook.blob_path)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Failed to physically move notebook file {notebook.blob_path}: {exc}")

    actor = _current_actor(user)
    notebook.catalog_name = body.target_catalog
    notebook.schema_name = body.target_schema
    notebook.schema_id = target_schema.id
    notebook.name = dest_name
    notebook.updated_by = actor
    
    db.commit()
    db.refresh(notebook)
    return notebook


async def delete_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str) -> None:
    notebook = get_notebook(db, catalog_name, schema_name, notebook_name)
    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()

    # Delete from storage
    await _delete_notebook_file(db, schema, notebook.blob_path)

    db.delete(notebook)
    db.commit()


def delete_schema(db: Session, catalog_name: str, schema_name: str) -> None:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    # Check if there are any notebooks blocking deletion
    blocking_notebooks = db.query(UnifiedCatalogNotebook).filter(
        UnifiedCatalogNotebook.schema_id == schema.id
    ).all()
    if blocking_notebooks:
        names = ", ".join([nb.name for nb in blocking_notebooks])
        raise ValueError(f"Cannot delete schema '{schema_name}' because it contains registered notebooks: {names}.")

    # Check if there are any dashboards blocking deletion
    blocking_dashboards = db.query(UnifiedCatalogDashboard).filter(
        UnifiedCatalogDashboard.schema_id == schema.id
    ).all()
    if blocking_dashboards:
        names = ", ".join([db_item.name for db_item in blocking_dashboards])
        raise ValueError(f"Cannot delete schema '{schema_name}' because it contains registered dashboards: {names}.")

    db.delete(schema)
    db.commit()


# ── Postgres Catalog Sync ─────────────────────────────────────────────────────

def sync_postgres_catalog(db: Session, catalog_name: str, triggered_by: str) -> dict:
    """Walk a postgres catalog via information_schema and persist schemas,
    tables, and columns into the catalog tables, then enqueue embeddings.

    Returns a summary dict: {schemas_synced, tables_synced, columns_synced}.
    """
    import logging as _log
    logger = _log.getLogger(__name__)

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found")
    if catalog.catalog_type != "postgres":
        raise ValueError(f"Catalog '{catalog_name}' is not a postgres catalog")
    if not catalog.connection_id or not catalog.database_name:
        raise ValueError(f"Catalog '{catalog_name}' has no connection_id or database_name configured")

    record = _get_connection(db, catalog.connection_id)
    pg_conn = _connect_record(record, catalog.database_name)

    try:
        cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch all user schemas
        cur.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema',
                                       'pg_toast', 'catalog_search')
              AND schema_name NOT LIKE 'pg_temp_%'
              AND schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER BY schema_name
            """
        )
        remote_schemas = [r["schema_name"] for r in cur.fetchall()]

        # Fetch all tables in one query
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema',
                                       'pg_toast', 'catalog_search')
              AND table_schema NOT LIKE 'pg_temp_%'
            ORDER BY table_schema, table_name
            """
        )
        remote_tables = cur.fetchall()

        # Fetch all columns in one query
        cur.execute(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema',
                                       'pg_toast', 'catalog_search')
              AND table_schema NOT LIKE 'pg_temp_%'
            ORDER BY table_schema, table_name, ordinal_position
            """
        )
        remote_columns = cur.fetchall()
    finally:
        pg_conn.close()

    # Build column map: (schema, table) -> [col_dicts]
    col_map: dict[tuple[str, str], list[dict]] = {}
    for col in remote_columns:
        key = (col["table_schema"], col["table_name"])
        col_map.setdefault(key, []).append(dict(col))

    from app.catalog.search_indexer import enqueue_asset_for_embedding

    schemas_synced = 0
    tables_synced = 0
    columns_synced = 0

    # Group tables by schema
    tables_by_schema: dict[str, list] = {}
    for tbl in remote_tables:
        tables_by_schema.setdefault(tbl["table_schema"], []).append(tbl["table_name"])

    for schema_name in remote_schemas:
        # Upsert schema row
        schema_row = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
            .first()
        )
        if not schema_row:
            schema_row = UnifiedCatalogSchema(
                catalog_id=catalog.id,
                name=schema_name,
                created_by=triggered_by,
            )
            db.add(schema_row)
            db.flush()
        schemas_synced += 1

        for table_name in tables_by_schema.get(schema_name, []):
            # Upsert table row
            table_row = (
                db.query(UnifiedCatalogTable)
                .filter(UnifiedCatalogTable.schema_id == schema_row.id, UnifiedCatalogTable.name == table_name)
                .first()
            )
            if not table_row:
                table_row = UnifiedCatalogTable(
                    schema_id=schema_row.id,
                    name=table_name,
                    table_type=CatalogTableType.POSTGRES_NATIVE,
                    connection_id=catalog.connection_id,
                    source_database=catalog.database_name,
                    pg_schema=schema_name,
                    pg_table=table_name,
                    owner=triggered_by,
                    created_by=triggered_by,
                )
                db.add(table_row)
                db.flush()
            else:
                # Update connection info in case it changed
                table_row.connection_id = catalog.connection_id
                table_row.source_database = catalog.database_name
                table_row.pg_schema = schema_name
                table_row.pg_table = table_name
                db.flush()
            tables_synced += 1

            # Replace columns (delete + insert)
            db.query(UnifiedCatalogColumn).filter(UnifiedCatalogColumn.table_id == table_row.id).delete()
            cols = col_map.get((schema_name, table_name), [])
            for col in cols:
                db.add(UnifiedCatalogColumn(
                    table_id=table_row.id,
                    name=col["column_name"],
                    data_type=col["data_type"],
                    nullable=(col["is_nullable"] == "YES"),
                    ordinal=col["ordinal_position"],
                ))
            columns_synced += len(cols)

            # Enqueue embedding
            col_summary = ", ".join(
                f"{c['column_name']} ({c['data_type']})" for c in cols
            ) if cols else None
            try:
                enqueue_asset_for_embedding(
                    db,
                    object_type="table",
                    source_object_id=table_row.id,
                    catalog_name=catalog_name,
                    schema_name=schema_name,
                    object_name=table_name,
                    content_summary=col_summary,
                )
            except Exception as emb_err:
                logger.warning("Failed to enqueue embedding for %s.%s.%s: %s", catalog_name, schema_name, table_name, emb_err)

    db.commit()
    logger.info("Postgres catalog sync done: catalog=%s schemas=%d tables=%d columns=%d", catalog_name, schemas_synced, tables_synced, columns_synced)
    return {"schemas_synced": schemas_synced, "tables_synced": tables_synced, "columns_synced": columns_synced}


# ── Catalog Dashboard Services ───────────────────────────────────────────────

def list_dashboards(db: Session, catalog_name: str, schema_name: str) -> list[UnifiedCatalogDashboard]:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    return db.query(UnifiedCatalogDashboard).filter(UnifiedCatalogDashboard.schema_id == schema.id).order_by(UnifiedCatalogDashboard.name).all()


def get_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str) -> UnifiedCatalogDashboard:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    dashboard = db.query(UnifiedCatalogDashboard).filter(
        UnifiedCatalogDashboard.schema_id == schema.id,
        UnifiedCatalogDashboard.name == dashboard_name
    ).first()
    if not dashboard:
        raise ValueError(f"Dashboard '{dashboard_name}' not found in schema '{catalog_name}.{schema_name}'.")
    return dashboard


async def create_dashboard(db: Session, catalog_name: str, schema_name: str, body: DashboardCreate, user: dict) -> UnifiedCatalogDashboard:
    from uuid import uuid4
    from app.dashboards.models.dashboard import Dashboard

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    # Check for name namespace conflict
    existing = db.query(UnifiedCatalogDashboard).filter(
        UnifiedCatalogDashboard.catalog_name == catalog_name,
        UnifiedCatalogDashboard.schema_name == schema_name,
        UnifiedCatalogDashboard.name == body.name
    ).first()
    if existing:
        raise ValueError(f"Dashboard '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

    actor = _current_actor(user)

    # Create both the dashboard JSON and the catalog metadata in the account DB.
    dash_id = str(uuid4())
    first_page_id = str(uuid4())
    dashboard_record = Dashboard(
        id=dash_id,
        name=body.name,
        folder_id=None,
        permission_mode="individual",
        is_draft=True,
        pages=[{
            "id": first_page_id,
            "dashboardId": dash_id,
            "name": "Page 1",
            "order": 0,
            "layout": [],
        }],
        widgets=[],
        datasets=[],
        settings=None,
        created_by=actor,
    )
    catalog_dashboard = UnifiedCatalogDashboard(
        schema_id=schema.id,
        catalog_name=catalog_name,
        schema_name=schema_name,
        name=body.name,
        dashboard_id=dash_id,
        owner=actor,
        comment=body.comment,
        created_by=actor,
        updated_by=actor,
    )
    db.add(dashboard_record)
    db.add(catalog_dashboard)
    db.commit()
    db.refresh(catalog_dashboard)

    # Enqueue embedding for semantic search
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="dashboard",
            source_object_id=catalog_dashboard.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=catalog_dashboard.name,
            description=catalog_dashboard.comment,
        )
        db.commit()
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for dashboard %s: %s", catalog_dashboard.name, _idx_err)

    return catalog_dashboard


def update_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardUpdate, user: dict) -> UnifiedCatalogDashboard:
    from app.dashboards.models.dashboard import Dashboard

    catalog_dashboard = get_dashboard(db, catalog_name, schema_name, dashboard_name)
    actor = _current_actor(user)

    if body.comment is not None:
        catalog_dashboard.comment = body.comment
    if body.owner is not None:
        catalog_dashboard.owner = body.owner

    if body.name is not None and body.name != catalog_dashboard.name:
        # Check name uniqueness in target schema
        existing = db.query(UnifiedCatalogDashboard).filter(
            UnifiedCatalogDashboard.catalog_name == catalog_name,
            UnifiedCatalogDashboard.schema_name == schema_name,
            UnifiedCatalogDashboard.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Dashboard '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
        catalog_dashboard.name = body.name

        # Also rename in system dashboard table if it exists
        if catalog_dashboard.dashboard_id:
            system_dash = db.query(Dashboard).filter(Dashboard.id == catalog_dashboard.dashboard_id).first()
            if system_dash:
                system_dash.name = body.name

    catalog_dashboard.updated_by = actor
    db.commit()
    db.refresh(catalog_dashboard)

    # Re-enqueue embedding whenever name or comment changes
    if body.name is not None or body.comment is not None:
        try:
            from app.catalog.search_indexer import enqueue_asset_for_embedding
            enqueue_asset_for_embedding(
                db,
                object_type="dashboard",
                source_object_id=catalog_dashboard.id,
                catalog_name=catalog_dashboard.catalog_name,
                schema_name=catalog_dashboard.schema_name,
                object_name=catalog_dashboard.name,
                description=catalog_dashboard.comment,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            _log.getLogger(__name__).warning("Failed to re-enqueue embedding for dashboard %s: %s", catalog_dashboard.name, _idx_err)

    return catalog_dashboard


async def move_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardMove, user: dict) -> UnifiedCatalogDashboard:
    catalog_dashboard = get_dashboard(db, catalog_name, schema_name, dashboard_name)

    target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
    if not target_catalog:
        raise ValueError(f"Target catalog '{body.target_catalog}' not found.")
    
    target_schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == target_catalog.id,
        UnifiedCatalogSchema.name == body.target_schema
    ).first()
    if not target_schema:
        raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

    dest_name = body.new_name if body.new_name else catalog_dashboard.name

    # Check for name uniqueness in target schema
    existing = db.query(UnifiedCatalogDashboard).filter(
        UnifiedCatalogDashboard.catalog_name == body.target_catalog,
        UnifiedCatalogDashboard.schema_name == body.target_schema,
        UnifiedCatalogDashboard.name == dest_name
    ).first()
    if existing:
        raise ValueError(f"Dashboard '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

    actor = _current_actor(user)
    catalog_dashboard.catalog_name = body.target_catalog
    catalog_dashboard.schema_name = body.target_schema
    catalog_dashboard.schema_id = target_schema.id
    catalog_dashboard.name = dest_name
    catalog_dashboard.updated_by = actor

    # Also rename the system dashboard if name changed
    if body.new_name and catalog_dashboard.dashboard_id:
        from app.dashboards.models.dashboard import Dashboard
        system_dash = db.query(Dashboard).filter(Dashboard.id == catalog_dashboard.dashboard_id).first()
        if system_dash:
            system_dash.name = dest_name

    db.commit()
    db.refresh(catalog_dashboard)
    return catalog_dashboard


async def delete_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str) -> None:
    from app.dashboards.models.dashboard import Dashboard

    catalog_dashboard = get_dashboard(db, catalog_name, schema_name, dashboard_name)

    # Delete system dashboard from system DB
    if catalog_dashboard.dashboard_id:
        system_dash = db.query(Dashboard).filter(Dashboard.id == catalog_dashboard.dashboard_id).first()
        if system_dash:
            db.delete(system_dash)

    # Delete search indexing entry
    try:
        from app.catalog.search_indexer import delete_asset_from_search
        delete_asset_from_search(db, "dashboard", catalog_dashboard.id)
    except Exception as _idx_err:
        import logging as _log
        _log.getLogger(__name__).warning("Failed to delete embedding for dashboard %s: %s", catalog_dashboard.name, _idx_err)

    db.delete(catalog_dashboard)
    db.commit()


# ── Queries ───────────────────────────────────────────────────────────────────

def list_queries(db: Session, catalog_name: str, schema_name: str) -> list[UnifiedCatalogQuery]:
    schema = db.query(UnifiedCatalogSchema).join(
        UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id
    ).filter(
        UnifiedCatalog.name == catalog_name,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    return db.query(UnifiedCatalogQuery).options(
        joinedload(UnifiedCatalogQuery.versions)
    ).filter(
        UnifiedCatalogQuery.schema_id == schema.id
    ).order_by(UnifiedCatalogQuery.created_at.desc()).all()


async def create_query(db: Session, catalog_name: str, schema_name: str, body: QueryCreate, user: dict) -> UnifiedCatalogQuery:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        raise ValueError(f"Catalog '{catalog_name}' not found.")
    schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == catalog.id,
        UnifiedCatalogSchema.name == schema_name
    ).first()
    if not schema:
        raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

    # Check for duplicate name in this catalog & schema
    existing = db.query(UnifiedCatalogQuery).filter(
        UnifiedCatalogQuery.catalog_name == catalog_name,
        UnifiedCatalogQuery.schema_name == schema_name,
        UnifiedCatalogQuery.name == body.name
    ).first()
    if existing:
        raise ValueError(f"Query '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

    actor = _current_actor(user)

    catalog_query = UnifiedCatalogQuery(
        schema_id=schema.id,
        catalog_name=catalog_name,
        schema_name=schema_name,
        name=body.name,
        sql_text=body.sql_text,
        owner=actor,
        description=body.description,
        current_version=1,
        created_by=actor,
        updated_by=actor,
    )
    db.add(catalog_query)
    db.flush()

    # Automatically create version 1
    v1 = UnifiedCatalogQueryVersion(
        query_id=catalog_query.id,
        version=1,
        sql_text=body.sql_text,
        description=body.description,
        change_summary="Initial version",
        created_by=actor,
    )
    db.add(v1)
    db.commit()
    db.refresh(catalog_query)

    # Enqueue embedding for semantic search
    q_name = catalog_query.name
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="query",
            source_object_id=catalog_query.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=catalog_query.name,
            description=catalog_query.description or catalog_query.sql_text,
        )
        db.commit()
    except Exception as _idx_err:
        db.rollback()
        import logging as _log
        _log.getLogger(__name__).warning("Failed to enqueue embedding for query %s: %s", q_name, _idx_err)

    return catalog_query


def get_query(db: Session, catalog_name: str, schema_name: str, query_name: str) -> UnifiedCatalogQuery:
    query_obj = db.query(UnifiedCatalogQuery).options(
        joinedload(UnifiedCatalogQuery.versions)
    ).filter(
        UnifiedCatalogQuery.catalog_name == catalog_name,
        UnifiedCatalogQuery.schema_name == schema_name,
        UnifiedCatalogQuery.name == query_name
    ).first()
    if not query_obj:
        raise ValueError(f"Query '{query_name}' not found in schema '{catalog_name}.{schema_name}'.")
    return query_obj


def update_query(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryUpdate, user: dict) -> UnifiedCatalogQuery:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)
    actor = _current_actor(user)

    if body.owner is not None:
        catalog_query.owner = body.owner
    if body.description is not None:
        catalog_query.description = body.description

    # If SQL text changed, create a new version automatically
    if body.sql_text is not None and body.sql_text != catalog_query.sql_text:
        highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
            UnifiedCatalogQueryVersion.query_id == catalog_query.id
        ).scalar() or catalog_query.current_version
        next_v = highest_v + 1
        new_v = UnifiedCatalogQueryVersion(
            query_id=catalog_query.id,
            version=next_v,
            sql_text=body.sql_text,
            description=body.description or catalog_query.description,
            change_summary=body.change_summary or f"Updated query to version {next_v}",
            created_by=actor,
        )
        db.add(new_v)
        catalog_query.sql_text = body.sql_text
        catalog_query.current_version = next_v

    if body.name is not None and body.name != catalog_query.name:
        existing = db.query(UnifiedCatalogQuery).filter(
            UnifiedCatalogQuery.catalog_name == catalog_name,
            UnifiedCatalogQuery.schema_name == schema_name,
            UnifiedCatalogQuery.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Query '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
        catalog_query.name = body.name

    catalog_query.updated_by = actor
    db.commit()
    db.refresh(catalog_query)

    # Re-enqueue embedding whenever name, description, or SQL changes
    q_name = catalog_query.name
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="query",
            source_object_id=catalog_query.id,
            catalog_name=catalog_query.catalog_name,
            schema_name=catalog_query.schema_name,
            object_name=catalog_query.name,
            description=catalog_query.description or catalog_query.sql_text,
        )
        db.commit()
    except Exception as _idx_err:
        db.rollback()
        import logging as _log
        _log.getLogger(__name__).warning("Failed to re-enqueue embedding for query %s: %s", q_name, _idx_err)

    return catalog_query


def create_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryCreateVersion, user: dict) -> UnifiedCatalogQueryVersion:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)
    actor = _current_actor(user)

    highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
        UnifiedCatalogQueryVersion.query_id == catalog_query.id
    ).scalar() or catalog_query.current_version
    next_v = highest_v + 1

    new_v = UnifiedCatalogQueryVersion(
        query_id=catalog_query.id,
        version=next_v,
        sql_text=body.sql_text,
        description=body.description or catalog_query.description,
        change_summary=body.change_summary or f"Version {next_v}",
        created_by=actor,
    )
    db.add(new_v)
    catalog_query.sql_text = body.sql_text
    if body.description is not None:
        catalog_query.description = body.description
    catalog_query.current_version = next_v
    catalog_query.updated_by = actor

    db.commit()
    db.refresh(new_v)
    db.refresh(catalog_query)

    # Re-enqueue embedding
    try:
        from app.catalog.search_indexer import enqueue_asset_for_embedding
        enqueue_asset_for_embedding(
            db,
            object_type="query",
            source_object_id=catalog_query.id,
            catalog_name=catalog_query.catalog_name,
            schema_name=catalog_query.schema_name,
            object_name=catalog_query.name,
            description=catalog_query.description or catalog_query.sql_text,
        )
        db.commit()
    except Exception as _idx_err:
        db.rollback()
        import logging as _log
        _log.getLogger(__name__).warning("Failed to re-enqueue embedding for query %s: %s", catalog_query.name, _idx_err)

    return new_v


def list_query_versions(db: Session, catalog_name: str, schema_name: str, query_name: str) -> list[UnifiedCatalogQueryVersion]:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)
    return db.query(UnifiedCatalogQueryVersion).filter(
        UnifiedCatalogQueryVersion.query_id == catalog_query.id
    ).order_by(UnifiedCatalogQueryVersion.version.desc()).all()


def get_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int) -> UnifiedCatalogQueryVersion:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)
    v = db.query(UnifiedCatalogQueryVersion).filter(
        UnifiedCatalogQueryVersion.query_id == catalog_query.id,
        UnifiedCatalogQueryVersion.version == version_num
    ).first()
    if not v:
        raise ValueError(f"Version {version_num} not found for query '{query_name}'.")
    return v


def restore_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int, user: dict) -> UnifiedCatalogQuery:
    target_v = get_query_version(db, catalog_name, schema_name, query_name, version_num)
    catalog_query = get_query(db, catalog_name, schema_name, query_name)
    actor = _current_actor(user)

    highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
        UnifiedCatalogQueryVersion.query_id == catalog_query.id
    ).scalar() or catalog_query.current_version
    next_v = highest_v + 1

    new_v = UnifiedCatalogQueryVersion(
        query_id=catalog_query.id,
        version=next_v,
        sql_text=target_v.sql_text,
        description=target_v.description,
        change_summary=f"Restored from version {version_num}",
        created_by=actor,
    )
    db.add(new_v)
    catalog_query.sql_text = target_v.sql_text
    catalog_query.description = target_v.description
    catalog_query.current_version = next_v
    catalog_query.updated_by = actor

    db.commit()
    db.refresh(catalog_query)
    return catalog_query


async def move_query(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryMove, user: dict) -> UnifiedCatalogQuery:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)

    target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
    if not target_catalog:
        raise ValueError(f"Target catalog '{body.target_catalog}' not found.")
    
    target_schema = db.query(UnifiedCatalogSchema).filter(
        UnifiedCatalogSchema.catalog_id == target_catalog.id,
        UnifiedCatalogSchema.name == body.target_schema
    ).first()
    if not target_schema:
        raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

    dest_name = body.new_name if body.new_name else catalog_query.name

    existing = db.query(UnifiedCatalogQuery).filter(
        UnifiedCatalogQuery.catalog_name == body.target_catalog,
        UnifiedCatalogQuery.schema_name == body.target_schema,
        UnifiedCatalogQuery.name == dest_name
    ).first()
    if existing:
        raise ValueError(f"Query '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

    actor = _current_actor(user)
    catalog_query.catalog_name = body.target_catalog
    catalog_query.schema_name = body.target_schema
    catalog_query.schema_id = target_schema.id
    catalog_query.name = dest_name
    catalog_query.updated_by = actor

    db.commit()
    db.refresh(catalog_query)
    return catalog_query


async def delete_query(db: Session, catalog_name: str, schema_name: str, query_name: str) -> None:
    catalog_query = get_query(db, catalog_name, schema_name, query_name)

    # Delete search indexing entry
    try:
        from app.catalog.search_indexer import delete_asset_from_search
        delete_asset_from_search(db, "query", catalog_query.id)
    except Exception as _idx_err:
        db.rollback()
        import logging as _log
        _log.getLogger(__name__).warning("Failed to delete embedding for query %s: %s", catalog_query.name, _idx_err)

    db.delete(catalog_query)
    db.commit()




