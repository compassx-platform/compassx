"""Session tracker for semantic memory.

Tracks active session timeouts and handles session closure background jobs.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy import text
from app.config import settings
from app.memory.research_store import ResearchMemoryStore

logger = logging.getLogger(__name__)


class SessionTracker:
    """Tracks chat session activity, handles timeout detection and explicit closure tasks."""

    def __init__(self, store, extractor):
        """Initialize tracker with storage and LLM extraction delegates."""
        self.store = store
        self.extractor = extractor
        self._sessions = {}  # session_id -> {user_id, workspace_id, last_activity, is_closed}
        self._last_extracted_at = {}  # session_id -> datetime
        self._extraction_guard_seconds = 300  # 5 minutes minimum gap

        # Read timeout from settings
        self.inactivity_timeout_minutes = getattr(settings, "INACTIVITY_TIMEOUT_MINUTES", 30)

    def on_activity(self, session_id, user_id: str, workspace_id: str):
        """Refreshes or registers the session activity timestamp."""
        self._sessions[session_id] = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "last_activity": datetime.now(timezone.utc),
            "is_closed": False,
        }

    async def on_explicit_close(self, session_id):
        """Marks the session as closed and triggers immediate extraction."""
        if session_id in self._sessions:
            self._sessions[session_id]["is_closed"] = True
        await self._handle_session_end(session_id, reason="explicit_close")

    def _should_extract(self, session_id) -> bool:
        """Determines if extraction should run based on the minimum guard interval."""
        now = datetime.now(timezone.utc)
        last_extracted = self._last_extracted_at.get(session_id)
        if last_extracted and (now - last_extracted).total_seconds() < self._extraction_guard_seconds:
            return False

        self._last_extracted_at[session_id] = now
        return True

    async def _handle_session_end(self, session_id, reason: str):
        """Initiates the background fact extraction task if criteria are met."""
        try:
            session_id_int = int(session_id)
        except ValueError:
            logger.error("Invalid session_id format: %s", session_id)
            return

        db_session = self.store.db_pool()
        try:
            # Check if this session has already been successfully extracted
            log_query = text("""
                SELECT MAX(completed_at)
                FROM ai.memory_extraction_log
                WHERE session_id = :session_id AND status = 'done'
            """)
            last_completed = db_session.execute(log_query, {"session_id": str(session_id)}).scalar()

            if last_completed:
                # Check if there are any new user/assistant messages after the last completed extraction
                new_msg_query = text("""
                    SELECT COUNT(*)
                    FROM ai.chat_messages
                    WHERE session_id = :session_id AND role IN ('user', 'assistant') AND created_at > :last_completed
                """)
                new_msg_count = db_session.execute(new_msg_query, {
                    "session_id": session_id_int,
                    "last_completed": last_completed,
                }).scalar()
                
                if new_msg_count == 0:
                    logger.info("Session %s has no new messages since last extraction at %s, skipping", session_id, last_completed)
                    return

            query = text("""
                SELECT role, content
                FROM ai.chat_messages
                WHERE session_id = :session_id AND role IN ('user', 'assistant')
                ORDER BY created_at ASC
            """)
            rows = db_session.execute(query, {"session_id": session_id_int}).fetchall()
            turns = []
            for row in rows:
                role_val = row[0].value if hasattr(row[0], "value") else str(row[0])
                turns.append({"role": role_val, "content": row[1] or ""})
        except Exception as e:
            logger.error("Error fetching turns for session %s: %s", session_id, e)
            return
        finally:
            db_session.close()

        if len(turns) < 4:
            logger.info("Session %s has fewer than 4 turns (%d), skipping extraction", session_id, len(turns))
            return

        if not self._should_extract(session_id):
            logger.info("Extraction guard hit for session %s, skipping", session_id)
            return

        session_info = self._sessions.get(session_id)
        if session_info:
            user_id = session_info["user_id"]
            workspace_id = session_info["workspace_id"]
        else:
            user_id = "default_user"
            workspace_id = "default"

        # Fire background task
        asyncio.create_task(
            self._run_extraction(
                session_id=session_id,
                user_id=user_id,
                workspace_id=workspace_id,
                turns=turns,
                reason=reason,
            )
        )

        if session_id in self._sessions:
            del self._sessions[session_id]

    async def _run_extraction(self, session_id, user_id: str, workspace_id: str, turns: list[dict], reason: str):
        """Worker task to perform fact extraction and save entries to database."""
        log_id = None
        try:
            log_id = self.store.start_extraction_log(
                session_id=str(session_id),
                user_id=user_id,
                workspace_id=workspace_id,
                trigger=reason,
                turns_processed=len(turns),
            )

            facts = await self.extractor.extract(turns, user_id, workspace_id)
            stats = self.store.bulk_save(
                facts=facts,
                user_id=user_id,
                workspace_id=workspace_id,
                source="session_extraction",
                source_session_id=str(session_id),
            )

            stats["facts_extracted"] = len(facts)
            self.store.complete_extraction_log(log_id, stats)

            try:
                research_store = ResearchMemoryStore(self.store.db_pool)
                promotion_stats = research_store.promote_session_facts(
                    workspace_id=workspace_id,
                    source_session_id=str(session_id),
                    facts=facts,
                    source_agent=None,
                    source_type="notebook",
                    promoted_via="post_session_extraction",
                )
                self.store.complete_promotion_log(log_id, promotion_stats)
            except Exception as promotion_err:
                logger.error("Research memory promotion failed open for session %s: %s", session_id, promotion_err)
                try:
                    self.store.fail_promotion_log(log_id, str(promotion_err), evaluated_count=len(facts))
                except Exception as log_err:
                    logger.error("Failed to write promotion failure log: %s", log_err)

            logger.info("Successfully completed memory extraction for session %s. Stats: %s", session_id, stats)
        except Exception as e:
            logger.error("Error in async memory extraction task for session %s: %s", session_id, e)
            if log_id:
                try:
                    self.store.fail_extraction_log(log_id, str(e))
                except Exception as log_err:
                    logger.error("Failed to write extraction failure log: %s", log_err)

    async def run_inactivity_checker(self):
        """Periodically scans active sessions and closes expired ones."""
        logger.info("Starting memory inactivity checker loop...")
        while True:
            try:
                await asyncio.sleep(60)
                now = datetime.now(timezone.utc)
                expired_sessions = []
                timeout_delta = timedelta(minutes=self.inactivity_timeout_minutes)

                for session_id, info in list(self._sessions.items()):
                    if info.get("is_closed"):
                        continue
                    if (now - info["last_activity"]) >= timeout_delta:
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    logger.info("Session %s timed out due to inactivity", session_id)
                    await self._handle_session_end(session_id, reason="inactivity_timeout")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in inactivity checker task: %s", e)


