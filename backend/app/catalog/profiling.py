"""Catalog-native profiling for assets that do not use DBConnection."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.models.agents import DataSourceProfile
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTable
from app.sql_warehouse.catalog.duckdb_resolver import build_duckdb_catalog_plan
from app.sql_warehouse.engine.duckdb_adapter import DuckDBAdapter


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


async def profile_iceberg_scope(
    db: Session, *, catalog_name: str, schema_name: str | None, table_name: str | None,
) -> None:
    """Profile Iceberg tables through the same DuckDB catalog views used by SQL warehouses."""
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    query = db.query(UnifiedCatalogTable, UnifiedCatalogSchema).join(
        UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id
    ).filter(UnifiedCatalogSchema.catalog_id == catalog.id)
    if schema_name:
        query = query.filter(UnifiedCatalogSchema.name == schema_name)
    if table_name:
        query = query.filter(UnifiedCatalogTable.name == table_name)
    tables = query.all()
    if table_name and not tables:
        raise ValueError(f"Table '{catalog_name}.{schema_name}.{table_name}' not found")

    adapter = DuckDBAdapter()
    setup = build_duckdb_catalog_plan(db).setup_sql
    summaries: list[dict[str, Any]] = []
    for table, schema in tables:
        fqn = ".".join(_quote(part) for part in (catalog_name, schema.name, table.name))
        result = await adapter.execute(
            sql=f"SELECT * FROM {fqn} LIMIT 1000", query_id=f"profile-{table.id}",
            timeout_sec=300, max_threads=None, max_memory_mb=None, setup_sql=setup,
        )
        count_result = await adapter.execute(
            sql=f"SELECT COUNT(*) AS row_count FROM {fqn}", query_id=f"profile-count-{table.id}",
            timeout_sec=300, max_threads=None, max_memory_mb=None, setup_sql=setup,
        )
        row_count = int(count_result.rows[0][0]) if count_result.rows else 0
        columns = []
        for index, name in enumerate(result.columns):
            values = [row[index] for row in result.rows]
            non_null = [value for value in values if value is not None]
            columns.append({
                "name": name,
                "data_type": next((column.data_type for column in table.columns if column.name == name), None),
                "null_count_sample": len(values) - len(non_null),
                "distinct_count_sample": len({repr(value) for value in non_null}),
                "sample_size": len(values),
            })
        profile = db.query(DataSourceProfile).filter(
            DataSourceProfile.connection_id.is_(None), DataSourceProfile.target_type == "table",
            DataSourceProfile.catalog_name == catalog_name, DataSourceProfile.schema_name == schema.name,
            DataSourceProfile.table_name == table.name,
        ).first()
        if not profile:
            profile = DataSourceProfile(connection_id=None, target_type="table", catalog_name=catalog_name, schema_name=schema.name, table_name=table.name)
            db.add(profile)
        profile.row_count = row_count
        profile.columns = columns
        profile.last_profiled_at = datetime.now(timezone.utc)
        summaries.append({"schema": schema.name, "table": table.name, "row_count": row_count, "column_count": len(columns)})

    target_type = "table" if table_name else ("schema" if schema_name else "catalog")
    if target_type != "table":
        aggregate = db.query(DataSourceProfile).filter(
            DataSourceProfile.connection_id.is_(None), DataSourceProfile.target_type == target_type,
            DataSourceProfile.catalog_name == catalog_name,
            DataSourceProfile.schema_name == schema_name if schema_name else DataSourceProfile.schema_name.is_(None),
            DataSourceProfile.table_name.is_(None),
        ).first()
        if not aggregate:
            aggregate = DataSourceProfile(connection_id=None, target_type=target_type, catalog_name=catalog_name, schema_name=schema_name)
            db.add(aggregate)
        aggregate.row_count = sum(item["row_count"] for item in summaries)
        aggregate.columns = summaries
        aggregate.domain_inference = {"table_count": len(summaries)}
        aggregate.last_profiled_at = datetime.now(timezone.utc)
    db.commit()
