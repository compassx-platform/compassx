"""MemoryStore for Structured Recall Memory (SRM).

Handles saving facts with overlap-based deduplication and logging of extraction tasks.
"""

import logging
import re
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def _tokenize(text_str: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric word tokens."""
    return set(re.findall(r"\w+", text_str.lower()))


class MemoryStore:
    """Provides SQL database operations for saving and retrieving agent semantic memories."""

    def __init__(self, db_pool: sessionmaker):
        """Initialize with an existing SQLAlchemy sessionmaker."""
        self.db_pool = db_pool

    def save(
        self,
        user_id: str,
        workspace_id: str,
        fact: str,
        fact_type: str,
        tags: list[str],
        confidence: float,
        tier: int,
        source: str,
        source_session_id: str | None = None,
    ) -> dict:
        """Save a fact to user memory, reinforcing it if a near-duplicate exists.

        Args:
            user_id: User identifier.
            workspace_id: Workspace identifier.
            fact: The text statement to remember.
            fact_type: Category of the fact.
            tags: List of metadata tags.
            confidence: Extraction confidence score (0.0 to 1.0).
            tier: Confidence tier (1 to 3).
            source: Source indicator (e.g. 'session_extraction').
            source_session_id: Source session identifier.

        Returns:
            dict: Description of the action performed ('created' or 'reinforced') and row ID.
        """
        db_session = self.db_pool()
        try:
            # 1. Fetch active facts of same type for user & workspace
            select_query = text("""
                SELECT id, fact, tags, confidence, reinforcement_count
                FROM ai.agent_memory
                WHERE user_id = :user_id
                  AND workspace_id = :workspace_id
                  AND fact_type = :fact_type
                  AND is_active = TRUE
            """)
            rows = db_session.execute(
                select_query,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "fact_type": fact_type,
                },
            ).fetchall()

            new_tokens = _tokenize(fact)
            match_id = None
            existing_tags = []

            # 2. Heuristic overlap check
            for row in rows:
                row_id, existing_fact, row_tags, _, _ = row
                existing_tokens = _tokenize(existing_fact)
                union = new_tokens.union(existing_tokens)
                intersection = new_tokens.intersection(existing_tokens)

                overlap = len(intersection) / len(union) if union else 0.0
                if overlap > 0.75:
                    match_id = row_id
                    existing_tags = row_tags or []
                    break

            if match_id:
                # Reinforce existing fact
                merged_tags = list(set(existing_tags) | set(tags))
                update_query = text("""
                    UPDATE ai.agent_memory
                    SET reinforcement_count = reinforcement_count + 1,
                        last_reinforced_at = NOW(),
                        confidence = LEAST(1.0, confidence + 0.05),
                        tags = :tags
                    WHERE id = :id
                """)
                db_session.execute(update_query, {"tags": merged_tags, "id": match_id})
                db_session.commit()
                logger.info("Reinforced existing memory fact ID: %s", match_id)
                return {"action": "reinforced", "id": str(match_id)}

            # Insert new fact
            insert_query = text("""
                INSERT INTO ai.agent_memory (
                    user_id, workspace_id, fact, fact_type, tags, confidence, tier, source, source_session_id
                ) VALUES (
                    :user_id, :workspace_id, :fact, :fact_type, :tags, :confidence, :tier, :source, :source_session_id
                ) RETURNING id
            """)
            res = db_session.execute(
                insert_query,
                {
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "fact": fact,
                    "fact_type": fact_type,
                    "tags": tags,
                    "confidence": confidence,
                    "tier": tier,
                    "source": source,
                    "source_session_id": source_session_id,
                },
            )
            new_id = res.scalar()
            db_session.commit()
            logger.info("Created new memory fact ID: %s", new_id)
            return {"action": "created", "id": str(new_id)}

        except Exception as e:
            db_session.rollback()
            logger.error("Database save failed in MemoryStore: %s", e)
            raise
        finally:
            db_session.close()

    def bulk_save(
        self,
        facts: list[dict],
        user_id: str,
        workspace_id: str,
        source: str,
        source_session_id: str | None = None,
    ) -> dict:
        """Save multiple facts sequentially.

        Returns:
            dict: Stats on number of created and merged facts.
        """
        created = 0
        merged = 0
        for f in facts:
            res = self.save(
                user_id=user_id,
                workspace_id=workspace_id,
                fact=f["fact"],
                fact_type=f["fact_type"],
                tags=f.get("tags", []),
                confidence=f.get("confidence", 1.0),
                tier=f.get("tier", 2),
                source=source,
                source_session_id=source_session_id,
            )
            if res["action"] == "created":
                created += 1
            else:
                merged += 1
        return {"facts_created": created, "facts_merged": merged}

    def start_extraction_log(
        self,
        session_id: str,
        user_id: str,
        workspace_id: str,
        trigger: str,
        turns_processed: int,
    ) -> str:
        """Log the start of an extraction run."""
        db_session = self.db_pool()
        try:
            query = text("""
                INSERT INTO ai.memory_extraction_log (
                    session_id, user_id, workspace_id, trigger, turns_processed, status, started_at
                ) VALUES (
                    :session_id, :user_id, :workspace_id, :trigger, :turns_processed, 'pending', NOW()
                ) RETURNING id
            """)
            res = db_session.execute(
                query,
                {
                    "session_id": str(session_id),
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "trigger": trigger,
                    "turns_processed": turns_processed,
                },
            )
            log_id = res.scalar()
            db_session.commit()
            return str(log_id)
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to start extraction log: %s", e)
            raise
        finally:
            db_session.close()

    def complete_extraction_log(self, log_id: str, stats: dict) -> None:
        """Update extraction log status to success with details."""
        db_session = self.db_pool()
        try:
            query = text("""
                UPDATE ai.memory_extraction_log
                SET status = 'done',
                    completed_at = NOW(),
                    facts_extracted = :facts_extracted,
                    facts_created = :facts_created,
                    facts_merged = :facts_merged
                WHERE id = :id
            """)
            db_session.execute(
                query,
                {
                    "id": log_id,
                    "facts_extracted": stats.get("facts_extracted", 0),
                    "facts_created": stats.get("facts_created", 0),
                    "facts_merged": stats.get("facts_merged", 0),
                },
            )
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to complete extraction log: %s", e)
            raise
        finally:
            db_session.close()

    def fail_extraction_log(self, log_id: str, error: str) -> None:
        """Update extraction log status to failure with error description."""
        db_session = self.db_pool()
        try:
            query = text("""
                UPDATE ai.memory_extraction_log
                SET status = 'failed',
                    error = :error,
                    completed_at = NOW()
                WHERE id = :id
            """)
            db_session.execute(query, {"id": log_id, "error": error})
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to mark extraction log as failed: %s", e)
            raise
        finally:
            db_session.close()

    def complete_promotion_log(self, log_id: str, stats: dict) -> None:
        """Update extraction log with successful research-memory promotion pass details."""
        db_session = self.db_pool()
        try:
            query = text("""
                UPDATE ai.memory_extraction_log
                SET promotion_pass_run_at = NOW(),
                    facts_evaluated_count = :facts_evaluated_count,
                    facts_promoted_count = :facts_promoted_count,
                    promotion_pass_status = 'completed',
                    promotion_pass_error = NULL
                WHERE id = :id
            """)
            db_session.execute(
                query,
                {
                    "id": log_id,
                    "facts_evaluated_count": stats.get("facts_evaluated_count", 0),
                    "facts_promoted_count": stats.get("facts_promoted_count", 0),
                },
            )
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to complete promotion log: %s", e)
            raise
        finally:
            db_session.close()

    def fail_promotion_log(self, log_id: str, error: str, evaluated_count: int = 0) -> None:
        """Update extraction log with failed research-memory promotion details."""
        db_session = self.db_pool()
        try:
            query = text("""
                UPDATE ai.memory_extraction_log
                SET promotion_pass_run_at = NOW(),
                    facts_evaluated_count = :facts_evaluated_count,
                    facts_promoted_count = 0,
                    promotion_pass_status = 'failed',
                    promotion_pass_error = :error
                WHERE id = :id
            """)
            db_session.execute(
                query,
                {
                    "id": log_id,
                    "facts_evaluated_count": evaluated_count,
                    "error": error,
                },
            )
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to mark promotion pass as failed: %s", e)
            raise
        finally:
            db_session.close()
