"""Foreign catalog sync — imports external Postgres schema metadata into
vector_db.assets so those tables become semantically searchable.

Per spec §5:
  - User has already registered a foreign connection via the existing
    connection-management flow.
  - User triggers a sync; this function runs in a BackgroundTask.
  - We query information_schema.tables + information_schema.columns on
    the external Postgres.
  - Each table is upserted into vector_db.assets with is_foreign=True
    and an embedding job is enqueued.
  - Cleanup of stale rows for removed tables is deferred (spec §9).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session

from app.catalog.search_indexer import enqueue_asset_for_embedding
from app.catalog.search_models import CatalogSearchForeignSyncLog

logger = logging.getLogger(__name__)


def _build_content_summary(columns: list[dict]) -> str | None:
    """Compose a column-name list for the embedding text (per spec §6)."""
    if not columns:
        return None
    parts = []
    for col in columns:
        name = col.get("column_name", "")
        dtype = col.get("data_type", "")
        parts.append(f"{name} ({dtype})" if dtype else name)
    return ", ".join(parts)


def sync_foreign_catalog(
    db: Session,
    *,
    connection_id: int,
    foreign_catalog_name: str,
    triggered_by_user_id: str,
) -> dict:
    """Synchronise schema metadata from an external Postgres connection.

    Creates a ``foreign_sync_log`` row, connects to the external DB,
    queries ``information_schema``, upserts assets, and enqueues embedding
    jobs.  Updates the log row on completion or failure.

    Returns a summary dict suitable for returning as an API response.
    """
    # 1. Insert sync log row
    sync_log = CatalogSearchForeignSyncLog(
        foreign_catalog_name=foreign_catalog_name,
        connection_id=connection_id,
        triggered_by_user_id=triggered_by_user_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    try:
        # 2. Fetch connection credentials
        from app.models.agents import DBConnection
        from app.agents.services.encryption import decrypt_field

        conn_row: DBConnection | None = db.query(DBConnection).filter(
            DBConnection.id == connection_id
        ).first()
        if conn_row is None:
            raise ValueError(f"DBConnection {connection_id} not found")

        host = conn_row.host
        port = conn_row.port or 5432
        db_name = conn_row.db_name or "postgres"
        username = decrypt_field(conn_row.username_enc) if conn_row.username_enc else ""
        password = decrypt_field(conn_row.password_enc) if conn_row.password_enc else ""

        # 3. Connect to external Postgres and fetch tables + columns
        pg_conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=db_name,
            user=username,
            password=password,
            connect_timeout=10,
        )
        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Fetch all user tables
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
            tables = cur.fetchall()

            # Fetch all columns in one query for efficiency
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema',
                                           'pg_toast', 'catalog_search')
                  AND table_schema NOT LIKE 'pg_temp_%'
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            all_columns = cur.fetchall()
        finally:
            pg_conn.close()

        # Build a lookup: (schema, table) -> [col_dicts]
        col_map: dict[tuple[str, str], list[dict]] = {}
        for col in all_columns:
            key = (col["table_schema"], col["table_name"])
            col_map.setdefault(key, []).append(dict(col))

        # 4. Upsert each table into vector_db.assets
        now = datetime.now(timezone.utc)
        synced = 0

        for tbl in tables:
            schema_name = tbl["table_schema"]
            table_name = tbl["table_name"]
            cols = col_map.get((schema_name, table_name), [])
            content_summary = _build_content_summary(cols)
            description = (
                f"Table {table_name} in schema {schema_name} "
                f"with {len(cols)} column(s)."
            ) if not content_summary else None

            # source_object_id: stable identifier using connection + schema + table
            source_object_id = f"foreign:{connection_id}:{schema_name}.{table_name}"

            try:
                enqueue_asset_for_embedding(
                    db,
                    object_type="foreign_table",
                    source_object_id=source_object_id,
                    catalog_name=foreign_catalog_name,
                    schema_name=schema_name,
                    object_name=table_name,
                    description=description,
                    content_summary=content_summary,
                    is_foreign=True,
                    last_synced_at=now,
                )
                synced += 1
            except Exception as exc:
                logger.warning(
                    "Failed to index foreign table %s.%s: %s",
                    schema_name,
                    table_name,
                    exc,
                )

        db.commit()

        # 5. Update sync log to completed
        sync_log.status = "completed"
        sync_log.tables_synced = synced
        sync_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Foreign catalog sync completed: connection_id=%s, tables_synced=%s",
            connection_id,
            synced,
        )
        return {
            "sync_log_id": sync_log.id,
            "status": "completed",
            "tables_synced": synced,
        }

    except Exception as exc:
        db.rollback()
        logger.error("Foreign catalog sync failed: %s", exc, exc_info=True)

        # Re-fetch log after rollback and mark failed
        try:
            sync_log = db.get(CatalogSearchForeignSyncLog, sync_log.id)
            if sync_log:
                sync_log.status = "failed"
                sync_log.error_message = str(exc)[:2000]
                sync_log.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass

        raise
