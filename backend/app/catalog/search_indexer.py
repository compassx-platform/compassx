"""Catalog search indexer — upsert assets and enqueue embedding jobs.

Called from catalog save handlers (create_table, create_volume, etc.)
within the same DB transaction.  Non-blocking: the caller commits; the
async embedding worker picks up the job afterwards.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.catalog.embedding_service import compose_embedding_text
from app.catalog.search_models import CatalogSearchAsset, CatalogSearchEmbeddingJob

# Updated whenever the DB schema changes (migration 0004 sets vector(1536))
_EMBEDDING_MODEL_TAG = "llm-connection"

logger = logging.getLogger(__name__)


def enqueue_asset_for_embedding(
    db: Session,
    *,
    object_type: str,
    source_object_id: str,
    catalog_name: str,
    schema_name: str,
    object_name: str,
    description: str | None = None,
    content_summary: str | None = None,
    is_foreign: bool = False,
    last_synced_at: datetime | None = None,
) -> CatalogSearchAsset:
    """Upsert a catalog object into ``vector_db.assets`` and enqueue an
    embedding job.

    If the asset already exists (matched by ``source_object_id + object_type``),
    its metadata is refreshed and ``embedding`` is set back to NULL so the
    worker re-embeds it with the new text.

    Returns the upserted :class:`CatalogSearchAsset` row.
    """
    embedding_text = compose_embedding_text(
        object_type=object_type,
        object_name=object_name,
        description=description,
        content_summary=content_summary,
    )

    # Upsert the asset row
    asset = (
        db.query(CatalogSearchAsset)
        .filter(
            CatalogSearchAsset.source_object_id == source_object_id,
            CatalogSearchAsset.object_type == object_type,
        )
        .first()
    )

    if asset is None:
        asset = CatalogSearchAsset(
            object_type=object_type,
            catalog_name=catalog_name,
            schema_name=schema_name,
            object_name=object_name,
            source_object_id=source_object_id,
            description=description,
            content_summary=content_summary,
            embedding_text=embedding_text,
            embedding=None,
            embedding_model=_EMBEDDING_MODEL_TAG,
            is_foreign=is_foreign,
            last_synced_at=last_synced_at,
        )
        db.add(asset)
    else:
        # Refresh metadata and reset embedding so the worker re-embeds
        asset.catalog_name = catalog_name
        asset.schema_name = schema_name
        asset.object_name = object_name
        asset.description = description
        asset.content_summary = content_summary
        asset.embedding_text = embedding_text
        asset.embedding = None  # forces re-embedding
        asset.embedding_model = _EMBEDDING_MODEL_TAG
        asset.is_foreign = is_foreign
        asset.updated_at = datetime.now(timezone.utc)
        if last_synced_at is not None:
            asset.last_synced_at = last_synced_at

    # Flush so asset.id is populated before we reference it
    db.flush()

    # Enqueue embedding job
    job = CatalogSearchEmbeddingJob(
        asset_id=asset.id,
        status="pending",
        attempts=0,
    )
    db.add(job)

    logger.debug(
        "Enqueued embedding job for %s %s.%s.%s (asset_id will be assigned on commit)",
        object_type,
        catalog_name,
        schema_name,
        object_name,
    )
    return asset


def delete_asset_from_search(
    db: Session,
    object_type: str,
    source_object_id: str,
) -> None:
    """Delete an asset and its pending/completed embedding jobs from the search index."""
    asset = (
        db.query(CatalogSearchAsset)
        .filter(
            CatalogSearchAsset.source_object_id == source_object_id,
            CatalogSearchAsset.object_type == object_type,
        )
        .first()
    )
    if asset is not None:
        db.query(CatalogSearchEmbeddingJob).filter(CatalogSearchEmbeddingJob.asset_id == asset.id).delete()
        db.delete(asset)
        logger.debug("Deleted asset %s (%s) from search index", source_object_id, object_type)

