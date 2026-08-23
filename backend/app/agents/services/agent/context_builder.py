"""Unified Context Builder — 3-Tier Layered Prompt Pipeline (Spec v2 Part D).

Layer 1: Platform Agent OS (Immutable Base Protocol & Rules)
Layer 2: User Instructions & Persona (Domain Persona & Specific Instructions)
Layer 3: Dynamic Runtime Context (Context Entries, Skills, Asset Manager, File Attachments)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentContextEntry
from app.agents.services.agent.system_prompts import (
    PLATFORM_AGENT_OS_PROMPT,
    SKILLS_STANDING_INSTRUCTION,
    ATTACHMENT_HANDLING_DIRECTIVE,
)


@dataclass
class PromptResult:
    """Encapsulates the fully assembled prompt and runtime tool requirements."""
    system_prompt: str
    has_attachment_tool_fetch: bool = False


def build_agent_system_prompt(
    db: Session,
    agent: Agent,
    session_id: int | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> PromptResult:
    """Return the fully assembled, 3-tier system prompt and attachment tool metadata."""
    parts: list[str] = []

    # ── Layer 1: Platform Agent OS (Immutable Base Protocol) ──────────────────
    parts.append(PLATFORM_AGENT_OS_PROMPT.strip())

    # ── Layer 2: User Instructions & Persona ──────────────────────────────────
    if agent.prompt and agent.prompt.strip():
        parts.append(f"## Custom Agent Persona & Domain Instructions\n{agent.prompt.strip()}")

    # ── Layer 3: Dynamic Runtime Context ──────────────────────────────────────
    # 3.1 Persistent Agent Context Entries
    agent_entries = (
        db.query(AgentContextEntry)
        .filter(
            AgentContextEntry.agent_id == agent.id,
            AgentContextEntry.is_active.is_(True),
        )
        .order_by(AgentContextEntry.version.desc())
        .all()
    )
    if agent_entries:
        ctx_text = "\n".join(e.text for e in agent_entries)
        parts.append(f"## Agent Workspace Context\n{ctx_text}")

    # 3.2 Standing Skills Instructions
    if hasattr(agent, "skills") and agent.skills:
        parts.append(SKILLS_STANDING_INSTRUCTION.strip())

    # 3.3 Runtime Asset Manager Context
    if runtime_context:
        runtime_section = _build_runtime_context_section(runtime_context)
        if runtime_section:
            parts.append(runtime_section)

    # 3.4 Session File Attachments & Vision Directives
    has_tool_fetch = False
    if session_id:
        attachment_section, has_tool_fetch = _build_attachment_section(db, session_id)
        if attachment_section:
            parts.append(attachment_section)

    full_system_prompt = "\n\n---\n\n".join(parts)
    return PromptResult(
        system_prompt=full_system_prompt,
        has_attachment_tool_fetch=has_tool_fetch,
    )


def build_system_prompt(db: Session, agent: Agent) -> str:
    """Backward-compatible helper returning raw system prompt string."""
    return build_agent_system_prompt(db, agent).system_prompt


def _build_runtime_context_section(runtime_context: dict[str, Any]) -> str | None:
    """Build the runtime frontend context prompt section."""
    if not runtime_context:
        return None

    if runtime_context.get("source") == "asset_manager":
        selected_asset_id = runtime_context.get("selected_asset_id")
        selected_asset_type_id = runtime_context.get("selected_asset_type_id")
        lines = [
            "## Current Asset Manager Context",
            f"Selected asset id: {selected_asset_id if selected_asset_id else 'none'}",
            f"Selected asset type id: {selected_asset_type_id if selected_asset_type_id else 'none'}",
        ]
        if selected_asset_id:
            lines.append(
                "When the user says 'this asset' or 'selected asset', treat it as "
                f"asset_id={selected_asset_id}. Use the asset_manager tool to fetch "
                "the asset details before explaining it."
            )
        return "\n".join(lines)

    return f"## Current Frontend Context\n{json.dumps(runtime_context, default=str)[:2000]}"


def _build_attachment_section(db: Session, session_id: int) -> tuple[str | None, bool]:
    """Build the session attachment inventory and directive block."""
    from app.models.agents import NovaAttachment, RagDocument
    from app.nova.services.attachment_service import get_context_payload

    attachments = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.status == "ready")
        .all()
    )
    rag_docs = (
        db.query(RagDocument)
        .filter(RagDocument.session_id == session_id)
        .all()
    )

    if not attachments and not rag_docs:
        return None, False

    attachment_blocks = ["## Attached Session Files"]
    has_tool_fetch = False

    for att in attachments:
        payload = get_context_payload(att.file_id, db)
        p_type = payload.get("type")
        if p_type == "inline":
            attachment_blocks.append(
                f"### File Attachment: {payload.get('filename')} (ID: {payload.get('file_id')})\n"
                f"Content:\n```\n{payload.get('content')}\n```"
            )
        elif p_type == "multimodal_native":
            attachment_blocks.append(
                f"### File Attachment: {payload.get('filename')} (ID: {payload.get('file_id')}, Image/Multimodal)\n"
                f"[Native image attached with visual pixels available]"
            )
        elif p_type == "tool_fetch":
            has_tool_fetch = True
            attachment_blocks.append(
                f"### File Attachment: {payload.get('filename')} (ID: {payload.get('file_id')})\n"
                f"Type: {payload.get('mime_type')}, Size: {payload.get('size_bytes')} bytes, Token Count: {payload.get('token_count')}\n"
                f"Preview:\n```\n{payload.get('preview_text')}\n```\n"
                f"Note: Full content is available via fetch_attachment(file_id='{payload.get('file_id')}', page=..., query=..., line_start=..., line_end=...)."
            )

    for rdoc in rag_docs:
        ext = (rdoc.filename or "").rsplit(".", 1)[-1].lower() if "." in (rdoc.filename or "") else ""
        is_img = (rdoc.mime_type and rdoc.mime_type.startswith("image/")) or ext in ("png", "jpg", "jpeg", "webp", "gif", "svg")
        if is_img:
            attachment_blocks.append(
                f"### Attached Image: {rdoc.filename} (Doc ID: {rdoc.id})\n"
                f"Size: {rdoc.size_bytes} bytes, Type: {rdoc.mime_type or f'image/{ext}'}\n"
                f"Content:\n```\n{rdoc.extracted_preview or f'[Image attached: {rdoc.filename}]'}\n```"
            )
        else:
            has_tool_fetch = True
            preview_text = rdoc.extracted_preview or ""
            attachment_blocks.append(
                f"### Attached Document: {rdoc.filename} (Doc ID: {rdoc.id})\n"
                f"Size: {rdoc.size_bytes} bytes\n"
                f"Content Preview:\n```\n{preview_text}\n```\n"
                f"Note: Full content is available via fetch_attachment(file_id='{rdoc.id}', page=..., query=..., line_start=..., line_end=...)."
            )

    attachment_blocks.append(ATTACHMENT_HANDLING_DIRECTIVE.strip())
    return "\n\n".join(attachment_blocks), has_tool_fetch



