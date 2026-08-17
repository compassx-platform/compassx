"""Memory orchestrator — single entry point for Semantic Recall Memory."""

import asyncio
import logging
from app.memory.session_tracker import SessionTracker

logger = logging.getLogger(__name__)


class MemoryOrchestrator:
    """Orchestrates memory tracking, inactivity checking, and close handling."""

    def __init__(self, session_tracker: SessionTracker):
        """Initialize orchestrator with its session tracker."""
        self.session_tracker = session_tracker

    async def on_activity(self, session_id, user_id: str, workspace_id: str):
        """Refresh the session's activity timestamp.

        Triggers whenever a user message is received or an agent response is written.
        """
        self.session_tracker.on_activity(session_id, user_id, workspace_id)

    async def on_explicit_close(self, session_id):
        """Explicitly end the session, triggering direct memory extraction.

        Called when a user closes a chat panel, starts a new conversation, or when the session close API is hit.
        """
        await self.session_tracker.on_explicit_close(session_id)

    def start_inactivity_checker(self):
        """Starts the background inactivity timeout checking loop as an asyncio task."""
        logger.info("Triggering start of memory inactivity checker background task...")
        asyncio.create_task(self.session_tracker.run_inactivity_checker())
