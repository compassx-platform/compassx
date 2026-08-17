#!/usr/bin/env python3
"""Data migration script to move Asset Manager tables from primary DB to separate Asset Manager DB."""

import argparse
import logging
import sys
from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.orm import sessionmaker

# Setup path so we can import app modules
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import AssetBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_assets")

TABLE_NAMES = [
    "am_asset_types",
    "am_tags_def",
    "am_asset_instances",
    "am_asset_versions",
    "am_asset_relationships",
    "am_asset_events",
    "am_asset_tags",
    "am_asset_documents",
    "am_asset_import_jobs",
    "am_asset_import_files",
    "am_asset_import_mapping_configs",
]


def _truncate_target_tables(target_conn, table_names):
    if not table_names:
        return
    qualified = ", ".join(table_names)
    target_conn.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE;"))


def migrate_data(source_url: str | None = None, target_url: str | None = None, drop_source: bool = False):
    source_url = source_url or settings.database_url
    target_url = target_url or settings.resolved_asset_db_url

    logger.info("Source database URL: %s", source_url)
    logger.info("Target database URL: %s", target_url)

    if source_url == target_url:
        logger.error("Source and Target database URLs are identical. No migration needed.")
        sys.exit(1)

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    # Import models to register metadata
    import app.asset_manager.models.asset_manager  # noqa: F401

    # 1. Ensure target tables exist.
    logger.info("Ensuring target database tables exist...")
    AssetBase.metadata.create_all(bind=target_engine)
    logger.info("Target database tables ready.")

    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    target_metadata = MetaData()
    target_metadata.reflect(bind=target_engine)

    # 2. Wipe target data first so we can safely re-import everything
    logger.info("Clearing existing target data...")
    with target_engine.begin() as target_conn:
        _truncate_target_tables(target_conn, TABLE_NAMES)
    logger.info("Target data cleared.")

    # 3. Migrate each table in dependency order
    logger.info("Migrating table data...")
    with target_engine.begin() as target_conn:
        for table_name in TABLE_NAMES:
            if table_name not in source_metadata.tables:
                logger.warning("Table '%s' not found in source database, skipping.", table_name)
                continue

            src_table = Table(table_name, source_metadata, autoload_with=source_engine)
            tgt_table = Table(table_name, target_metadata, autoload_with=target_engine)

            # Read from source. Asset instances are ordered so parent rows are inserted first.
            with source_engine.connect() as source_conn:
                query = select(src_table)
                if table_name == "am_asset_instances" and "depth" in src_table.c:
                    query = query.order_by(
                        src_table.c.depth.asc(),
                        src_table.c.parent_id.asc().nullsfirst(),
                        src_table.c.id.asc(),
                    )
                rows = source_conn.execute(query).fetchall()

            if not rows:
                logger.info("Table '%s' has no rows to migrate.", table_name)
                continue

            # Insert into target
            insert_data = [dict(row._mapping) for row in rows]
            target_conn.execute(tgt_table.insert(), insert_data)
            logger.info("Successfully migrated %d rows for table '%s'.", len(rows), table_name)

    # 4. Handle source table dropping if requested
    if drop_source:
        logger.info("Cleaning up source database tables...")
        with source_engine.begin() as source_conn:
            for table_name in reversed(TABLE_NAMES):
                if table_name in source_metadata.tables:
                    source_conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE;"))
                    logger.info("Dropped source table '%s'.", table_name)
        logger.info("Source database cleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Migrate Asset Manager tables to a separate database.")
    parser.add_argument(
        "--source-url",
        default=None,
        help="Explicit SQLAlchemy URL for the source database. Defaults to PG_* env settings.",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Explicit SQLAlchemy URL for the target Asset Manager database. Defaults to ASSET_DB_URL or derived PG_* settings.",
    )
    parser.add_argument(
        "--drop-source",
        action="store_true",
        help="Drop the asset manager tables from the source database after successful copy.",
    )
    args = parser.parse_args()

    migrate_data(source_url=args.source_url, target_url=args.target_url, drop_source=args.drop_source)
    logger.info("Migration complete!")


if __name__ == "__main__":
    main()
