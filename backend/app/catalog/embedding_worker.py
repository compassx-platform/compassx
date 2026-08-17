"""Async embedding worker for catalog semantic search.

Polls ``vector_db.embedding_jobs`` for pending rows, calls the
configured embedding LLM connection, and writes the resulting vector back into
``vector_db.assets.embedding``.

Retry policy: up to MAX_ATTEMPTS failures before marking a job
permanently ``failed``.  Failed jobs leave the asset with a NULL
embedding (excluded from search) until the asset is next updated and
re-enqueued.

Usage (started from main.py lifespan):
    from app.catalog.embedding_worker import start_embedding_worker
    start_embedding_worker(AccountSessionLocal)
"""
from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.catalog.embedding_service import get_embedding
from app.catalog.search_models import CatalogSearchAsset, CatalogSearchEmbeddingJob

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 5


def _process_one_job(db: Session) -> bool:
    """Claim and process a single pending embedding job.

    Returns True if a job was processed (regardless of success/failure),
    False if the queue was empty.
    """
    # Claim the oldest pending job
    job: CatalogSearchEmbeddingJob | None = (
        db.query(CatalogSearchEmbeddingJob)
        .filter(CatalogSearchEmbeddingJob.status == "pending")
        .order_by(CatalogSearchEmbeddingJob.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        return False

    job.status = "in_progress"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()

    asset: CatalogSearchAsset | None = db.get(CatalogSearchAsset, job.asset_id)
    if asset is None:
        # Asset was deleted — clean up the orphaned job
        db.delete(job)
        db.commit()
        return True

    try:
        vector = get_embedding(asset.embedding_text)

        if vector is None:
            # API key missing or transient failure
            raise RuntimeError(
                "get_embedding returned None — check your LLM connection and embedding model setup"
            )

        asset.embedding = vector
        asset.updated_at = datetime.now(timezone.utc)
        job.status = "completed"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Embedded %s %s.%s.%s (asset_id=%s)",
            asset.object_type,
            asset.catalog_name,
            asset.schema_name,
            asset.object_name,
            asset.id,
        )

    except Exception as exc:
        db.rollback()

        # Re-fetch after rollback
        job = db.get(CatalogSearchEmbeddingJob, job.id)
        if job is None:
            return True

        job.attempts += 1
        job.error_message = str(exc)[:2000]
        job.updated_at = datetime.now(timezone.utc)

        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            logger.error(
                "Embedding job %s permanently failed after %s attempts: %s",
                job.id,
                job.attempts,
                exc,
            )
        else:
            job.status = "pending"
            logger.warning(
                "Embedding job %s failed (attempt %s/%s): %s — will retry",
                job.id,
                job.attempts,
                MAX_ATTEMPTS,
                exc,
            )

        db.commit()

    return True


def _worker_loop(session_factory: Callable[[], Session]) -> None:
    """Main polling loop. Runs in a daemon thread."""
    logger.info("Catalog embedding worker started (poll_interval=%ss)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            db: Session = session_factory()
            try:
                processed = _process_one_job(db)
            finally:
                db.close()

            if not processed:
                # Queue empty — sleep before next poll
                time.sleep(POLL_INTERVAL_SECONDS)

        except Exception as exc:
            logger.error("Embedding worker loop error: %s", exc, exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS)


def start_embedding_worker(session_factory: sessionmaker) -> threading.Thread:
    """Start the embedding worker as a background daemon thread.

    The thread exits automatically when the main process does.

    Args:
        session_factory: SQLAlchemy ``sessionmaker`` bound to the account DB
                         (``AccountSessionLocal``).

    Returns:
        The started :class:`threading.Thread`.
    """
    thread = threading.Thread(
        target=_worker_loop,
        args=(session_factory,),
        name="catalog-embedding-worker",
        daemon=True,
    )
    thread.start()
    logger.info("Catalog embedding worker thread started (tid=%s)", thread.ident)
    return thread
