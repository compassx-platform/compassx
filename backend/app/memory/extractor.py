"""Fact extractor — parses semantic memories from chat history using LLM."""

import json
import logging
import re
from app.models.agents import LLMConnection

logger = logging.getLogger(__name__)

# Verbatim extraction prompt
EXTRACTION_PROMPT = """You are a memory extraction system for a data platform used in the renewable energy sector.

Given a conversation between a user and a data platform agent, extract persistent facts about the user that would be useful in future sessions.

Focus on extracting:
- Data assets they work with (tables, pipelines, databases, schemas, connections)
- Technical preferences and conventions (SQL style, language preference, naming)
- Goals and ongoing tasks (reports being built, pipelines being designed)
- Domain knowledge about their business (sector, metrics, terminology)
- Skills and experience level

Rules:
- Only extract facts that are persistent and reusable across future sessions
- Do not extract transient facts (e.g. errors encountered today, current mood)
- Each fact must be a single self-contained sentence — no pronouns, use full names
- Be specific — include table names, column names, values where mentioned
- Assign tags that would help retrieve this fact in future (3-6 tags per fact)
- Confidence: 1.0 if explicitly stated, 0.8 if strongly implied, 0.6 if inferred
- If the conversation contains no persistent facts, return an empty array

Return ONLY a JSON array with no preamble, explanation, or markdown fences.

[
  {{
    "fact": "...",
    "fact_type": "asset | schema | preference | skill | goal | convention | domain",
    "tags": ["tag1", "tag2", "tag3"],
    "confidence": 0.9
  }}
]

Conversation:
{conversation}
"""


class FactExtractor:
    """Invokes LLM to extract persistent facts from conversation history."""

    def __init__(self, llm_client, db_pool=None):
        """Initialize with LLM chat_stream client and database pool."""
        self.llm_client = llm_client
        self.db_pool = db_pool

    async def extract(self, turns: list[dict], user_id: str, workspace_id: str) -> list[dict]:
        """Extract persistent facts from turns.

        Args:
            turns: List of {"role": "user"|"assistant", "content": str}
            user_id: User identifier.
            workspace_id: Workspace identifier.

        Returns:
            list[dict]: Extracted facts matching the output format schema.
        """
        if not self.db_pool:
            logger.error("Database pool not provided to FactExtractor")
            return []

        # 1. Resolve LLMConnection
        from app.database import AccountSessionLocal
        sys_db = AccountSessionLocal()
        try:
            conn = (
                sys_db.query(LLMConnection)
                .filter(LLMConnection.use_for_memory.is_(True))
                .first()
            )
            if not conn:
                conn = (
                    sys_db.query(LLMConnection)
                    .filter(LLMConnection.is_fallback.is_(True))
                    .order_by(LLMConnection.id.asc())
                    .first()
                )
            if not conn:
                conn = sys_db.query(LLMConnection).order_by(LLMConnection.id.asc()).first()
            if conn:
                sys_db.expunge(conn)
        finally:
            sys_db.close()

        if not conn:
            logger.error("No LLMConnection found in database for memory extraction")
            return []

        # Force max_tokens to 2000
        conn.max_tokens = 2000

        # 2. Build conversation string
        conversation_str = ""
        for turn in turns:
            role = "User" if turn["role"] == "user" else "Agent"
            content = turn["content"]
            conversation_str += f"{role}: {content}\n"

        prompt = EXTRACTION_PROMPT.format(conversation=conversation_str)

        # 3. Call LLM
        logger.info("Triggering LLM fact extraction for session")
        full_text = ""
        try:
            # chat_stream expects list of messages
            messages = [{"role": "user", "content": prompt}]
            async for chunk in self.llm_client(conn, messages):
                if chunk["type"] == "text":
                    full_text += chunk["delta"]
        except Exception as e:
            logger.error("LLM call failed during fact extraction: %s", e)
            raise RuntimeError(f"LLM call failed: {e}") from e

        # 4. Clean and parse output
        cleaned_text = full_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_text)
            cleaned_text = re.sub(r"\n```$", "", cleaned_text)
            cleaned_text = cleaned_text.strip()

        try:
            facts = json.loads(cleaned_text)
            if not isinstance(facts, list):
                logger.error("LLM output is not a list: %s", cleaned_text)
                return []

            # Basic validation of facts structure
            valid_facts = []
            for f in facts:
                if isinstance(f, dict) and "fact" in f and "fact_type" in f:
                    f["tags"] = f.get("tags") or []
                    f["confidence"] = f.get("confidence") or 1.0
                    f["tier"] = 2  # default high-confidence tier
                    valid_facts.append(f)

            logger.info("Successfully extracted %d facts", len(valid_facts))
            return valid_facts
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Failed to parse JSON response from LLM: %s. Raw: %s", e, full_text)
            raise RuntimeError(f"Failed to parse JSON response from LLM: {e}. Raw text: {full_text[:200]}") from e
