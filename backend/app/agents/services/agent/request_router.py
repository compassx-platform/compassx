"""Request Router Service classifying user requests per Part B1."""

from __future__ import annotations

import re
from typing import Any, Dict, Literal, Optional
from app.agents.schemas.agent_manifest import AgentManifest

RequestCategory = Literal["informational", "single_action", "multi_stage_build"]


class RequestRouter:
    """Classifies incoming user messages before agent invocation."""

    MULTI_STAGE_VERBS = {"build", "create", "set up", "setup", "implement", "construct", "deploy"}
    MULTI_STAGE_NOUNS = {"pipeline", "dag", "medallion", "architecture", "suite", "system", "tables", "notebooks"}
    INFORMATIONAL_VERBS = {"show", "list", "check", "explain", "get", "describe", "what is", "where is", "how to"}

    def classify_request(
        self,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        agent_manifest: Optional[AgentManifest] = None,
    ) -> RequestCategory:
        manifest = agent_manifest or AgentManifest()

        # D10/B1: If planning is disabled, multi_stage_build is not reachable
        if not manifest.capabilities.planning.enabled:
            # Distinguish informational vs single_action
            lower_msg = user_message.lower()
            if any(verb in lower_msg for verb in self.INFORMATIONAL_VERBS):
                return "informational"
            return "single_action"

        lower_msg = user_message.lower()

        # Heuristic 1: Verbs like "build", "create", "implement" + multi-stage nouns -> multi_stage_build
        has_multi_verb = any(re.search(rf"\b{verb}\b", lower_msg) for verb in self.MULTI_STAGE_VERBS)
        has_multi_noun = any(re.search(rf"\b{noun}\b", lower_msg) for noun in self.MULTI_STAGE_NOUNS)

        if has_multi_verb and has_multi_noun:
            return "multi_stage_build"

        # Heuristic 2: Read-only single noun target + single verb (show, list, check, explain) -> informational
        has_info_verb = any(re.search(rf"\b{verb}\b", lower_msg) for verb in self.INFORMATIONAL_VERBS)
        if has_info_verb and not has_multi_verb:
            return "informational"

        # Default fallback
        return "single_action"
