"""Research Memory store and promotion helpers."""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

RESEARCH_FACT_TYPES = {
    "organizational_context",
    "business_priority",
    "deployment_convention",
    "operational_constraint",
    "rejected_proposal_context",
    "strategic_decision",
    "data_trust_signal",
}

PROMOTION_MIN_CONFIDENCE = 0.8

_DATABASE_DERIVABLE_TERMS = {
    "table", "column", "schema", "row", "rows", "relationship", "foreign key",
    "primary key", "date range", "tag definition", "tag_def", "completeness",
}

_GENERIC_DOMAIN_TERMS = {
    "iec", "standard kpi", "industry benchmark", "typical formula", "standard formula",
}

_SUPERCESSION_HINTS = {
    "now", "revised", "changed", "updated", "instead", "no longer", "override", "replaced",
}

_TYPE_KEYWORDS = [
    ("rejected_proposal_context", ("rejected", "declined", "do not re-propose", "do not repropose", "already has")),
    ("strategic_decision", ("decided", "skip", "proceed directly", "platform direction", "scope")),
    ("deployment_convention", ("defines", "definition", "calculation must", "client uses", "convention", "exclude", "include")),
    ("business_priority", ("priority", "focus", "deprioritize", "penalty", "guarantee", "this quarter")),
    ("operational_constraint", ("constraint", "scheduled", "restart", "workflow", "limitation", "do not flag")),
    ("data_trust_signal", ("unreliable", "reliable", "sensor", "exclude from", "trust", "quality")),
    ("organizational_context", ("contract", "ppa", "team", "stakeholder", "business model", "revenue")),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.lower()))


def _overlap(a: str, b: str) -> float:
    left = _tokenize(a)
    right = _tokenize(b)
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _normalize_confidence(value: float | Decimal | str | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _looks_like_supersession(new_fact: str, existing_fact: str) -> bool:
    new_lower = new_fact.lower()
    existing_lower = existing_fact.lower()
    overlap = _overlap(new_fact, existing_fact)
    has_update_hint = any(token in new_lower for token in _SUPERCESSION_HINTS)
    return overlap > 0.35 and has_update_hint and new_lower != existing_lower


def classify_research_fact(fact: str, fallback_type: str | None = None) -> str | None:
    lowered = fact.lower()
    for fact_type, keywords in _TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return fact_type
    if fallback_type in RESEARCH_FACT_TYPES:
        return fallback_type
    if fallback_type in {"convention", "domain"}:
        return "deployment_convention"
    if fallback_type == "goal":
        return "business_priority"
    return None


def qualifies_for_research_memory(fact: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    text_value = str(fact.get("fact") or "").strip()
    if not text_value:
        return False, None, "empty fact"

    confidence = _normalize_confidence(fact.get("confidence"))
    if confidence < PROMOTION_MIN_CONFIDENCE:
        return False, None, "confidence below 0.8"

    lowered = text_value.lower()
    if any(term in lowered for term in _DATABASE_DERIVABLE_TERMS):
        return False, None, "database-derivable fact"
    if any(term in lowered for term in _GENERIC_DOMAIN_TERMS):
        return False, None, "generic domain knowledge"

    research_type = classify_research_fact(text_value, fact.get("fact_type"))
    if not research_type:
        return False, None, "not research-relevant"

    return True, research_type, None


class ResearchMemoryStore:
    """Database operations for Tier 2 Research Memory."""

    def __init__(self, db_pool: sessionmaker, close_sessions: bool = True):
        self.db_pool = db_pool
        self.close_sessions = close_sessions

    def fetch(
        self,
        workspace_id: str,
        fact_type: str | None = None,
        scope: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        db = self.db_pool()
        try:
            conditions = ["workspace_id = :workspace_id", "valid_to IS NULL"]
            params: dict[str, Any] = {"workspace_id": workspace_id, "limit": limit}
            if fact_type:
                conditions.append("fact_type = :fact_type")
                params["fact_type"] = fact_type
            if scope:
                conditions.append("scope = :scope")
                params["scope"] = scope
            if tags:
                conditions.append("tags && :tags")
                params["tags"] = [t.lower() for t in tags]

            rows = db.execute(text(f"""
                SELECT id, fact, fact_type, confidence, source_agent, source_session_id,
                       source_type, promoted_via, scope, tags, valid_from, last_confirmed_at,
                       confirmation_count, created_at
                FROM research_memory
                WHERE {" AND ".join(conditions)}
                ORDER BY confirmation_count DESC, last_confirmed_at DESC
                LIMIT :limit
            """), params).fetchall()
            return [
                {
                    "id": str(r[0]),
                    "fact": r[1],
                    "fact_type": r[2],
                    "confidence": float(r[3]),
                    "source_agent": r[4],
                    "source_session_id": r[5],
                    "source_type": r[6],
                    "promoted_via": r[7],
                    "scope": r[8],
                    "tags": r[9] or [],
                    "valid_from": r[10].isoformat() if r[10] else None,
                    "last_confirmed_at": r[11].isoformat() if r[11] else None,
                    "confirmation_count": r[12],
                    "created_at": r[13].isoformat() if r[13] else None,
                }
                for r in rows
            ]
        finally:
            if self.close_sessions:
                db.close()

    def save(
        self,
        workspace_id: str,
        fact: str,
        fact_type: str,
        confidence: float,
        source_agent: str | None,
        source_session_id: str | None,
        source_type: str,
        promoted_via: str,
        scope: str = "workspace",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if fact_type not in RESEARCH_FACT_TYPES:
            raise ValueError(f"Unsupported research memory fact_type: {fact_type}")
        if confidence < PROMOTION_MIN_CONFIDENCE:
            raise ValueError("Research memory confidence must be at least 0.8")

        db = self.db_pool()
        try:
            active_rows = db.execute(text("""
                SELECT id, fact, tags, confirmation_count
                FROM research_memory
                WHERE workspace_id = :workspace_id
                  AND fact_type = :fact_type
                  AND scope = :scope
                  AND valid_to IS NULL
            """), {"workspace_id": workspace_id, "fact_type": fact_type, "scope": scope}).fetchall()

            normalized_tags = sorted({str(t).lower() for t in (tags or []) if str(t).strip()})
            for row in active_rows:
                if _overlap(fact, row[1]) > 0.75:
                    merged_tags = sorted(set(row[2] or []) | set(normalized_tags))
                    db.execute(text("""
                        UPDATE research_memory
                        SET confirmation_count = confirmation_count + 1,
                            last_confirmed_at = NOW(),
                            confidence = GREATEST(confidence, :confidence),
                            tags = :tags
                        WHERE id = :id
                    """), {"id": row[0], "confidence": confidence, "tags": merged_tags})
                    db.commit()
                    return {"action": "reinforced", "id": str(row[0])}

            for row in active_rows:
                if _looks_like_supersession(fact, row[1]):
                    insert_result = db.execute(text("""
                        INSERT INTO research_memory (
                            workspace_id, fact, fact_type, confidence, source_agent, source_session_id,
                            source_type, promoted_via, scope, tags, valid_from, last_confirmed_at
                        ) VALUES (
                            :workspace_id, :fact, :fact_type, :confidence, :source_agent, :source_session_id,
                            :source_type, :promoted_via, :scope, :tags, NOW(), NOW()
                        ) RETURNING id
                    """), {
                        "workspace_id": workspace_id,
                        "fact": fact,
                        "fact_type": fact_type,
                        "confidence": confidence,
                        "source_agent": source_agent,
                        "source_session_id": source_session_id,
                        "source_type": source_type,
                        "promoted_via": promoted_via,
                        "scope": scope,
                        "tags": normalized_tags,
                    })
                    new_id = insert_result.scalar()
                    db.execute(text("""
                        UPDATE research_memory
                        SET valid_to = NOW(),
                            superseded_by = :new_id
                        WHERE id = :old_id
                    """), {"new_id": new_id, "old_id": row[0]})
                    db.commit()
                    return {"action": "superseded", "id": str(new_id), "superseded_id": str(row[0])}

            insert_result = db.execute(text("""
                INSERT INTO research_memory (
                    workspace_id, fact, fact_type, confidence, source_agent, source_session_id,
                    source_type, promoted_via, scope, tags, valid_from, last_confirmed_at
                ) VALUES (
                    :workspace_id, :fact, :fact_type, :confidence, :source_agent, :source_session_id,
                    :source_type, :promoted_via, :scope, :tags, NOW(), NOW()
                ) RETURNING id
            """), {
                "workspace_id": workspace_id,
                "fact": fact,
                "fact_type": fact_type,
                "confidence": confidence,
                "source_agent": source_agent,
                "source_session_id": source_session_id,
                "source_type": source_type,
                "promoted_via": promoted_via,
                "scope": scope,
                "tags": normalized_tags,
            })
            new_id = insert_result.scalar()
            db.commit()
            return {"action": "created", "id": str(new_id)}
        except Exception:
            db.rollback()
            raise
        finally:
            if self.close_sessions:
                db.close()

    def promote_session_facts(
        self,
        workspace_id: str,
        source_session_id: str,
        facts: list[dict[str, Any]],
        source_agent: str | None = None,
        source_type: str = "notebook",
        promoted_via: str = "post_session_extraction",
    ) -> dict[str, int]:
        evaluated = 0
        promoted = 0
        for fact in facts:
            evaluated += 1
            qualifies, research_type, reason = qualifies_for_research_memory(fact)
            if not qualifies or not research_type:
                logger.debug("Research memory promotion skipped: %s", reason)
                continue
            self.save(
                workspace_id=workspace_id,
                fact=fact["fact"],
                fact_type=research_type,
                confidence=_normalize_confidence(fact.get("confidence") or 1.0),
                source_agent=source_agent,
                source_session_id=source_session_id,
                source_type=source_type,
                promoted_via=promoted_via,
                scope=fact.get("scope") or "workspace",
                tags=fact.get("tags") or [],
            )
            promoted += 1
        return {"facts_evaluated_count": evaluated, "facts_promoted_count": promoted}

    def harvest_recent_agent_memory(self, workspace_id: str, days: int = 30, limit: int = 200) -> dict[str, int]:
        db = self.db_pool()
        try:
            rows = db.execute(text("""
                SELECT fact, fact_type, tags, confidence, source, source_session_id
                FROM ai.agent_memory
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                  AND source != 'session_extraction'
                  AND created_at >= NOW() - (:days || ' days')::interval
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"workspace_id": workspace_id, "days": days, "limit": limit}).fetchall()
        finally:
            if self.close_sessions:
                db.close()

        facts = [
            {
                "fact": r[0],
                "fact_type": r[1],
                "tags": r[2] or [],
                "confidence": r[3],
                "source": r[4],
                "source_session_id": r[5],
            }
            for r in rows
        ]
        return self.promote_session_facts(
            workspace_id=workspace_id,
            source_session_id="engine_harvest",
            facts=facts,
            source_type="research_engine",
            promoted_via="engine_harvest",
        )


