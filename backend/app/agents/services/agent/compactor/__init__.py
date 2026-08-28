"""Agent Watermark Compaction Module."""

from app.agents.services.agent.compactor.session_compactor import (
    ConversationTurn,
    compact_session_history,
    group_messages_into_turns,
    partition_turns_for_compaction,
    preflight_watermark_check,
)
from app.agents.services.agent.compactor.summary_schema import (
    STRUCTURED_SUMMARY_SCHEMA,
    SUMMARY_SYSTEM_PROMPT,
    build_compaction_user_prompt,
)
from app.agents.services.agent.compactor.token_estimator import (
    DEFAULT_HIGH_WATERMARK_RATIO,
    DEFAULT_LOW_WATERMARK_K,
    estimate_messages_tokens,
    estimate_text_tokens,
    resolve_model_context_window,
)

__all__ = [
    "ConversationTurn",
    "compact_session_history",
    "group_messages_into_turns",
    "partition_turns_for_compaction",
    "preflight_watermark_check",
    "STRUCTURED_SUMMARY_SCHEMA",
    "SUMMARY_SYSTEM_PROMPT",
    "build_compaction_user_prompt",
    "DEFAULT_HIGH_WATERMARK_RATIO",
    "DEFAULT_LOW_WATERMARK_K",
    "estimate_messages_tokens",
    "estimate_text_tokens",
    "resolve_model_context_window",
]
