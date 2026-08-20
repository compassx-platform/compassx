"""Agent orchestrator — the main turn loop.

orchestrate_stream() is an async generator that yields SSE-compatible
event dicts. Callers (chat_stream_routes) forward these to the frontend
via Server-Sent Events.

Event types emitted:
  {"type": "text",       "delta": str, "agent_id": int, "agent_name": str,
                          "agent_color": str|None, "invocation_depth": int}
  {"type": "tool_start", "tool_name": str, "args": dict}
  {"type": "tool_end",   "tool_name": str, "result": dict, "ok": bool}
  {"type": "error",      "message": str}
  {"type": "done",       "usage": dict, "session_id": int, "message_id": int}
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy.orm import Session, selectinload

from app.models.agents import (
    Agent,
    AgentGitConnection,
    AgentTool,
    ChatMessage,
    ChatSession,
    LLMConnection,
    MessageRole,
)
from app.agents.services.agent.context_builder import build_system_prompt
from app.services.llm_client import chat_stream
from app.agents.services.agent.tool_executor import execute_tool
from app.asset_manager.schemas.agent_context import AssetManagerContextRequest
from app.asset_manager.services.agent_context_resolver import AssetManagerContextResolver
from app.agents.schemas.agent_manifest import AgentManifest, BaseProfile
from app.agents.services.agent.request_router import RequestRouter
from app.agents.services.agent.write_gating_middleware import WriteGatingMiddleware, WriteGatingViolation
from app.agents.services.agent.plan_service import PlanService
from app.agents.services.agent.known_assets_registry import registry as _asset_registry, register_from_tool_result

logger = logging.getLogger(__name__)

# Maximum messages to include in context window (sliding window)
_MAX_HISTORY_MESSAGES = 40


# ── Subagent result dataclass ─────────────────────────────────────────────────

@dataclass
class SubagentResult:
    """Return value from orchestrate_subagent_stream()."""
    agent_id: int
    agent_name: str
    last_output: str
    message_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_agent(db: Session, agent_id: int) -> Agent | None:
    """Load agent with all required relationships."""
    return (
        db.query(Agent)
        .options(
            selectinload(Agent.tools),
            selectinload(Agent.db_connections),
            selectinload(Agent.git_connections),
            selectinload(Agent.skills),
        )
        .filter(Agent.id == agent_id)
        .first()
    )


def _build_extra_tools(
    agent: Agent,
    enabled_tool_keys: list[str],
    session_id: int,
    invocation_depth: int,
    db: Session,
    loop: asyncio.AbstractEventLoop,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, BaseTool]:
    """Instantiate per-request stateful tools if the agent has them enabled.

    Returns a dict keyed by tool.key, to be passed to execute_tool() as
    extra_tools.  Currently only InvokeAgentTool is stateful; all other
    tools live in the global singleton TOOL_MAP.
    """
    extra: dict[str, BaseTool] = {}

    if "invoke_agent" in enabled_tool_keys:
        from app.agents.services.agent.tools.invoke_agent_tool import InvokeAgentTool

        extra["invoke_agent"] = InvokeAgentTool(
            session_id=session_id,
            invoking_agent_name=agent.name,
            invocation_depth=invocation_depth,
            db=db,
            _loop=loop,
            user_id=user_id,
            workspace_id=workspace_id,
        )

    if "fetch_memory" in enabled_tool_keys:
        from app.agents.services.agent.tools.fetch_memory_tool import FetchMemoryTool

        extra["fetch_memory"] = FetchMemoryTool(
            session_id=session_id,
            db=db,
            user_id=user_id,
            workspace_id=workspace_id,
        )

    if "fetch_research_memory" in enabled_tool_keys or "save_research_memory" in enabled_tool_keys:
        from app.agents.services.agent.tools.research_memory_tool import FetchResearchMemoryTool, SaveResearchMemoryTool

        if "fetch_research_memory" in enabled_tool_keys:
            extra["fetch_research_memory"] = FetchResearchMemoryTool(workspace_id=workspace_id)
        if "save_research_memory" in enabled_tool_keys:
            extra["save_research_memory"] = SaveResearchMemoryTool(session_id=session_id, workspace_id=workspace_id)

    research_context_tools = {
        "harvest_research_memory",
        "fetch_research_proposal_history",
    }
    if research_context_tools.intersection(enabled_tool_keys):
        from app.agents.services.agent.tools.research_engine_tools import (
            HarvestResearchMemoryTool,
            FetchResearchProposalHistoryTool,
        )

        if "harvest_research_memory" in enabled_tool_keys:
            extra["harvest_research_memory"] = HarvestResearchMemoryTool(workspace_id=workspace_id)
        if "fetch_research_proposal_history" in enabled_tool_keys:
            extra["fetch_research_proposal_history"] = FetchResearchProposalHistoryTool(workspace_id=workspace_id)

    if "save_data_profile" in enabled_tool_keys:
        from app.agents.services.agent.tools.profiling_tools import SaveDataProfileTool

        extra["save_data_profile"] = SaveDataProfileTool(
            session_id=session_id,
        )

    if "create_plan" in enabled_tool_keys:
        from app.agents.services.agent.tools.plan_tools import CreatePlanTool

        extra["create_plan"] = CreatePlanTool(
            session_id=session_id,
        )

    if "db_explorer" in enabled_tool_keys:
        from app.agents.services.agent.tools.db_explorer_tool import DatabaseExplorerTool

        extra["db_explorer"] = DatabaseExplorerTool(
            session_id=session_id,
        )

    if "escalate_to_plan" in enabled_tool_keys:
        from app.agents.services.agent.tools.escalate_plan_tool import EscalateToPlanTool

        extra["escalate_to_plan"] = EscalateToPlanTool(
            session_id=session_id,
        )

    # Discover promoted catalog tools for the workspace / manifest (External Agent Tools)
    try:
        from app.database import AccountSessionLocal
        from app.catalog.models import UnifiedCatalogTool
        from app.agents.services.agent.tools.external_catalog_tool import ExternalCatalogTool

        if AccountSessionLocal is not None:
            with AccountSessionLocal() as adb:
                catalog_tools = adb.query(UnifiedCatalogTool).all()
                for cat_tool in catalog_tools:
                    tool_key = cat_tool.name
                    # If specific tools are enabled for this agent, check if selected or default to all for Nova
                    is_nova = getattr(agent, "name", "").lower() == "nova" or getattr(agent, "id", "") == "ai-data-engineer"
                    is_enabled = is_nova or (tool_key in enabled_tool_keys) or (cat_tool.full_name in enabled_tool_keys) or (len(enabled_tool_keys) == 0)

                    if is_enabled and tool_key not in extra:
                        extra[tool_key] = ExternalCatalogTool(
                            tool_id=cat_tool.id,
                            name=cat_tool.name,
                            description=cat_tool.description or f"Unified Catalog Tool: {cat_tool.full_name}",
                            input_schema=cat_tool.param_schema,
                            pinned_version=cat_tool.current_version,
                            connection_dependencies=cat_tool.connection_dependencies,
                            session_id=str(session_id),
                            agent_type="nova" if is_nova else getattr(agent, "name", "agent"),
                            invoked_by=user_id,
                        )
    except Exception as exc:
        logger.warning("Could not load external catalog tools into manifest: %s", exc)

    return extra


def _tag_event(
    event: dict,
    agent: Agent,
    invocation_depth: int,
) -> dict:
    """Attach agent identity fields to a streamed event dict."""
    event["agent_id"] = agent.id
    event["agent_name"] = agent.name
    event["agent_color"] = agent.color
    event["invocation_depth"] = invocation_depth
    return event


# ── Primary orchestrator (unchanged public interface) ─────────────────────────

def _resolve_llm_connection(
    db: Session,
    agent: Agent,
    override_llm_connection_id: int | None = None,
) -> LLMConnection | None:
    """Resolve the chat-time LLM connection."""
    from app.database import AccountSessionLocal
    sys_db = AccountSessionLocal()
    try:
        if override_llm_connection_id is not None:
            conn = (
                sys_db.query(LLMConnection)
                .filter(LLMConnection.id == override_llm_connection_id)
                .first()
            )
            if conn:
                sys_db.expunge(conn)
            return conn

        if agent.llm_connection_id is not None:
            conn = (
                sys_db.query(LLMConnection)
                .filter(LLMConnection.id == agent.llm_connection_id)
                .first()
            )
            if conn:
                sys_db.expunge(conn)
                return conn

        fallback = (
            sys_db.query(LLMConnection)
            .filter(LLMConnection.is_fallback.is_(True))
            .order_by(LLMConnection.id.asc())
            .first()
        )
        if fallback:
            sys_db.expunge(fallback)
            return fallback

        conn = sys_db.query(LLMConnection).order_by(LLMConnection.id.asc()).first()
        if conn:
            sys_db.expunge(conn)
        return conn
    finally:
        sys_db.close()


def _resolve_runtime_context(context: dict | None) -> dict:
    """Resolve module-owned frontend context into prompt/tool-ready context."""
    if not isinstance(context, dict):
        return {}

    resolved = dict(context)
    asset_context = context.get("asset_manager")
    if isinstance(asset_context, dict):
        resolved_asset_context = AssetManagerContextResolver().resolve(
            AssetManagerContextRequest.model_validate(asset_context)
        )
        resolved = {**resolved, **resolved_asset_context}
    return resolved


def _append_runtime_context_prompt(system_prompt: str, runtime_context: dict) -> str:
    if not runtime_context:
        return system_prompt

    asset_context = runtime_context.get("asset_manager")
    if isinstance(asset_context, dict):
        selected_asset_id = asset_context.get("selected_asset_id")
        selected_asset_type_id = asset_context.get("selected_asset_type_id")
        lines = [
            "## Current Frontend Context",
            runtime_context.get("summary", "Asset Manager context is active."),
            f"Route: {asset_context.get('route') or runtime_context.get('route') or 'unknown'}",
            f"Mode: {asset_context.get('mode') or 'unknown'}",
            f"Selected asset id: {selected_asset_id if selected_asset_id else 'none'}",
            f"Selected asset type id: {selected_asset_type_id if selected_asset_type_id else 'none'}",
        ]
        if selected_asset_id:
            lines.append(
                "When the user says 'this asset' or 'selected asset', treat it as "
                f"asset_id={selected_asset_id}. Use the asset_manager tool to fetch "
                "the asset details before explaining it."
            )
        return f"{system_prompt}\n\n---\n\n" + "\n".join(lines)

    return f"{system_prompt}\n\n---\n\n## Current Frontend Context\n{json.dumps(runtime_context, default=str)[:2000]}"


def _append_attachment_context(system_prompt: str, session_id: int, db: Session) -> tuple[str, bool]:
    """Append context for session-attached files to system prompt and return whether fetch_attachment tool is needed."""
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
        return system_prompt, False

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
                f"[Native image attached with base64 data available]"
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
        has_tool_fetch = True
        preview_text = rdoc.extracted_preview or ""
        attachment_blocks.append(
            f"### Attached Document: {rdoc.filename} (Doc ID: {rdoc.id})\n"
            f"Size: {rdoc.size_bytes} bytes\n"
            f"Content Preview:\n```\n{preview_text}\n```\n"
            f"Note: Full content is available via fetch_attachment(file_id='{rdoc.id}', page=..., query=..., line_start=..., line_end=...)."
        )

    doc_instructions = (
        "### ⚠️ MANDATORY TOOL EXECUTION INSTRUCTIONS FOR ATTACHED DOCUMENTS:\n"
        "1. **AUTOMATIC TOOL CALL REQUIRED**: When an attached document is in `tool_fetch` mode or has multiple pages, YOUR VERY FIRST ACTION MUST BE A TOOL CALL to `fetch_attachment(file_id='<file_id>')` or `fetch_attachment(file_id='<file_id>', page=N)`.\n"
        "2. **DO NOT output a final prose response to the user** before calling `fetch_attachment` to read the document content.\n"
        "3. **DO NOT ask the user for more previews, pages, or OCR text**. You have server-side access to all pages via `fetch_attachment`.\n"
        "4. **DO NOT claim you cannot see remaining pages**. Call `fetch_attachment` to inspect every page of the document.\n"
        "5. **Deliver complete, multi-page structured explanations**:\n"
        "   - **Executive Summary & Portfolio Totals**: Report overall status, total AC capacity, total DC capacity, site counts, and key metrics.\n"
        "   - **Structured Markdown Tables**: Provide full tables for site-level capacity, state-level, regional manager, or category breakdowns.\n"
        "   - **Glossary & Acronyms**: Define all domain terms and abbreviations found in the document.\n"
    )

    updated_prompt = system_prompt + "\n\n---\n\n" + "\n\n".join(attachment_blocks) + "\n\n" + doc_instructions
    return updated_prompt, has_tool_fetch



async def orchestrate_stream(
    session_id: int,
    user_content: str,
    db: Session,
    sandbox: bool = False,
    llm_connection_id: int | None = None,
    context: dict | None = None,
    user_id: str = "default_user",
    workspace_id: str = "default",
) -> AsyncIterator[dict]:
    """
    Main agent turn loop.

    Args:
        session_id: ChatSession.id — provides agent context.
        user_content: The user's message text.
        db: SQLAlchemy session.
        sandbox: If True, skip persisting messages (used by Agent Builder test chat).
        context: Optional frontend/Nova context for future platform-aware tools.

    Yields dicts for SSE streaming.
    """
    # ── Load session + agent ──────────────────────────────────────────────────
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .first()
    )
    if not session:
        yield {"type": "error", "message": "Session not found"}
        return

    agent = _load_agent(db, session.agent_id)
    if not agent:
        yield {"type": "error", "message": "Agent not found"}
        return

    if agent.status == "paused":
        yield {"type": "error", "message": "Agent is paused due to budget exhaustion or admin action."}
        return

    from app.agents.services.budget_service import check_budget, BudgetExceededError
    try:
        if db.in_transaction():
            db.rollback()
    except Exception:
        pass

    try:
        check_budget(db, "agent", str(agent.id), workspace_id)
    except BudgetExceededError as e:
        yield {"type": "error", "message": str(e)}
        return
    except Exception as e:
        logger.error("Budget check failed for agent %s: %s", agent.id, e)
        try:
            db.rollback()
        except Exception:
            pass

    llm_connection = _resolve_llm_connection(db, agent, llm_connection_id)
    if not llm_connection:
        yield {"type": "error", "message": "No LLM connection configured"}
        return

    # ── Build system prompt ───────────────────────────────────────────────────
    runtime_context = _resolve_runtime_context(context)
    system_prompt = _append_runtime_context_prompt(build_system_prompt(db, agent), runtime_context)
    system_prompt, has_attachment_tool_fetch = _append_attachment_context(system_prompt, session_id, db)

    # ── Load conversation history ─────────────────────────────────────────────
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(_MAX_HISTORY_MESSAGES)
        .all()
    )
    history_rows.reverse()

    messages = []
    for row in history_rows:
        if row.role == MessageRole.tool:
            continue
        messages.append({"role": row.role, "content": row.content or "", "id": row.id})

    # ── Persist user message ──────────────────────────────────────────────────
    user_msg_id = None
    if not sandbox:
        user_msg = ChatMessage(
            session_id=session_id,
            role=MessageRole.user,
            content=user_content,
            agent_name=None,
            invocation_depth=0,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)
        user_msg_id = user_msg.id

    messages.append({"role": "user", "content": user_content, "id": user_msg_id})

    # Notify Memory Activity (always register session user/workspace mapping)
    try:
        from app.memory import memory_orchestrator
        if memory_orchestrator:
            await memory_orchestrator.on_activity(str(session_id), user_id, workspace_id)
    except Exception as e:
        logger.error("Failed to notify activity to memory orchestrator: %s", e)

    # ── Resolve Agent Manifest (Spec v2 Part C) ──────────────────────────────
    manifest_data = getattr(agent, "manifest", None) or {}
    if isinstance(manifest_data, dict) and manifest_data:
        manifest = AgentManifest.model_validate(manifest_data)
    else:
        manifest = AgentManifest.default_for_profile(BaseProfile.REACTIVE_AGENT, agent_id=str(agent.id), display_name=agent.name)

    # ── Request Router Classification (Part B1) ──────────────────────────────
    router = RequestRouter()
    request_category = router.classify_request(
        user_message=user_content,
        agent_manifest=manifest,
    )
    logger.info("Request classification for agent %s: %s", agent.id, request_category)

    # ── Build tool definitions for enabled tools ───────────────────────────────
    enabled_tool_keys = [t.tool_name for t in agent.tools]
    if has_attachment_tool_fetch and "fetch_attachment" not in enabled_tool_keys:
        enabled_tool_keys.append("fetch_attachment")
    # Auto-inject skills tools if agent has skills attached
    if agent.skills:
        if "list_available_skills" not in enabled_tool_keys:
            enabled_tool_keys.append("list_available_skills")
        if "read_skill" not in enabled_tool_keys:
            enabled_tool_keys.append("read_skill")

    # Auto-set approved_at on plan if user message contains approval keywords
    if any(user_content.lower().startswith(kw) for kw in ["approved", "approve", "yes, approve", "proceed"]):
        import os
        from app.agents.services.agent.plan_service import PlanService
        _plan_svc = PlanService()
        if os.path.exists(_plan_svc.storage_dir):
            for _fname in os.listdir(_plan_svc.storage_dir):
                if _fname.startswith("plan_") and _fname.endswith(".json"):
                    _p = _plan_svc.get_plan(_fname[5:-5])
                    if _p and _p.session_id == session_id and not _p.approved_at:
                        _plan_svc.approve_plan(_p.plan_id)
                        logger.info("Marked plan %s approved_at via approval message", _p.plan_id)

    # ── Active Plan Enforcement ──────────────────────────────────────────────
    from app.agents.services.agent.plan_service import PlanService
    plan_service = PlanService()
    active_plan = plan_service.get_active_plan_for_session(session_id)

    if active_plan:
        request_category = "multi_stage_build"
        logger.info("Session %s has active approved plan %s; enforcing multi_stage_build execution loop", session_id, active_plan.plan_id)

        # Inject system prompt directive forcing full execution loop through ALL steps
        active_step = plan_service.get_next_step(active_plan.plan_id)
        all_steps = active_plan.steps
        pending_count = sum(1 for s in all_steps if s.status in ("pending", "in_progress"))
        steps_summary = "\n".join(
            f"  Step {s.id} [{s.status}]: {s.description}" for s in all_steps
        )
        step_desc = f"Step {active_step.id}: {active_step.description}" if active_step else "ALL STEPS COMPLETE"
        plan_directive = (
            f"\n\n---\n\n## ACTIVE APPROVED PLAN - MANDATORY EXECUTION LOOP\n"
            f"Plan ID: '{active_plan.plan_id}'\n"
            f"Goal: {active_plan.goal}\n"
            f"Remaining steps to execute: {pending_count}\n\n"
            f"All Steps:\n{steps_summary}\n\n"
            f"CRITICAL RULES - FOLLOW WITHOUT EXCEPTION:\n"
            f"1. Execute ALL pending steps in sequence THIS TURN. Do NOT stop after completing one step.\n"
            f"2. For EACH pending step, in order:\n"
            f"   a. Call get_next_step(plan_id='{active_plan.plan_id}') to get the next pending step.\n"
            f"   b. Call mark_step(..., step_id=<id>, status='in_progress').\n"
            f"   c. Perform the actual work for that step (create notebooks, write Python code, etc).\n"
            f"   d. Call mark_step(..., step_id=<id>, status='done').\n"
            f"   e. IMMEDIATELY continue to the next step without pausing or asking.\n"
            f"3. STOP only when get_next_step returns completed=True.\n"
            f"4. Do NOT create a new plan. Do NOT ask for user approval again. START EXECUTING NOW.\n"
            f"\nFirst step to execute: {step_desc}\n"
        )
        system_prompt += plan_directive

    # Spec v2 Part C3 / D11: If planning is enabled or an active plan exists, ensure plan tools exist
    if active_plan or manifest.capabilities.planning.enabled or any(kw in user_content.lower() for kw in ["approve", "plan", "step", "proceed", "build"]):
        for plan_tool_name in ["create_plan", "get_plan", "get_next_step", "mark_step", "append_correction", "escalate_to_plan"]:
            if plan_tool_name not in enabled_tool_keys:
                enabled_tool_keys.append(plan_tool_name)

    from app.agents.services.agent.tools.registry import get_tool_definitions
    tools = get_tool_definitions(enabled_tool_keys)

    # ── Per-request stateful tools (e.g. InvokeAgentTool) ────────────────────
    loop = asyncio.get_event_loop()
    extra_tools = _build_extra_tools(
        agent=agent,
        enabled_tool_keys=enabled_tool_keys,
        session_id=session_id,
        invocation_depth=0,
        db=db,
        loop=loop,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    # Remove any sentinel definitions already added by get_tool_definitions,
    # then add the live instances (which carry runtime context).
    # This prevents "Tool names must be unique" errors from the LLM API.
    extra_keys = set(extra_tools.keys())
    tools = [t for t in tools if t["function"]["name"] not in extra_keys]
    for et in extra_tools.values():
        tools.append(et.to_openai_definition())


    # ── Auto-Prefetch Attachments (Server-Side) ─────────────────────────────
    # For any tool_fetch attachments or uploaded session documents, execute
    # fetch_attachment server-side RIGHT NOW and inject the full content as a
    # synthetic assistant+tool message pair BEFORE the first LLM call.
    if has_attachment_tool_fetch:
        from app.nova.services.attachment_service import get_context_payload, fetch_attachment_content
        from app.models.agents import NovaAttachment, RagDocument
        import json as _json

        # 1. Prefetch NovaAttachments
        prefetch_attachments = (
            db.query(NovaAttachment)
            .filter(NovaAttachment.session_id == session_id, NovaAttachment.status == "ready")
            .all()
        )
        for _att in prefetch_attachments:
            _payload = get_context_payload(_att.file_id, db)
            if _payload.get("type") != "tool_fetch":
                continue
            _file_id_str = str(_att.file_id)
            _filename = _att.filename
            try:
                _full_content = fetch_attachment_content(_att.file_id, db=db)
            except Exception as _exc:
                logger.warning("Auto-prefetch failed for attachment %s: %s", _file_id_str, _exc)
                continue

            # Synthetic tool_call id
            _call_id = f"prefetch_{_file_id_str[:8]}"

            # Truncate if needed to stay within LLM context limits (~80k chars ≈ ~20k tokens)
            _MAX_PREFETCH_CHARS = 80_000
            if len(_full_content) > _MAX_PREFETCH_CHARS:
                _full_content = (
                    _full_content[:_MAX_PREFETCH_CHARS]
                    + f"\n\n[... Document truncated at {_MAX_PREFETCH_CHARS} chars for context limits. "
                    f"Use fetch_attachment(file_id='{_file_id_str}', page=N) to read specific pages ...]"
                )

            # Insert as: assistant message with a tool_call, then tool result
            messages.insert(-1, {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _call_id,
                    "type": "function",
                    "function": {
                        "name": "fetch_attachment",
                        "arguments": _json.dumps({"file_id": _file_id_str}),
                    },
                }],
            })
            messages.insert(-1, {
                "role": "tool",
                "tool_call_id": _call_id,
                "name": "fetch_attachment",
                "content": _full_content,
            })
            logger.info(
                "Auto-prefetched attachment %s (%s) — %d chars injected into context",
                _file_id_str, _filename, len(_full_content),
            )

        # 2. Prefetch RagDocuments (uploaded via Document Upload in Agent Chat)
        prefetch_rag_docs = (
            db.query(RagDocument)
            .filter(RagDocument.session_id == session_id)
            .all()
        )
        for _rdoc in prefetch_rag_docs:
            _doc_id_str = str(_rdoc.id)
            _filename = _rdoc.filename
            try:
                _full_content = fetch_attachment_content(_rdoc.id, db=db)
            except Exception as _exc:
                logger.warning("Auto-prefetch failed for rag doc %s: %s", _doc_id_str, _exc)
                continue

            if not _full_content or _full_content.startswith("Error:"):
                if _rdoc.extracted_preview:
                    _full_content = _rdoc.extracted_preview
                else:
                    continue

            _call_id = f"prefetch_doc_{_doc_id_str}"
            _MAX_PREFETCH_CHARS = 80_000
            if len(_full_content) > _MAX_PREFETCH_CHARS:
                _full_content = (
                    _full_content[:_MAX_PREFETCH_CHARS]
                    + f"\n\n[... Document truncated at {_MAX_PREFETCH_CHARS} chars for context limits. "
                    f"Use fetch_attachment(file_id='{_doc_id_str}', page=N) to read specific pages ...]"
                )

            messages.insert(-1, {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _call_id,
                    "type": "function",
                    "function": {
                        "name": "fetch_attachment",
                        "arguments": _json.dumps({"file_id": _doc_id_str}),
                    },
                }],
            })
            messages.insert(-1, {
                "role": "tool",
                "tool_call_id": _call_id,
                "name": "fetch_attachment",
                "content": _full_content,
            })
            logger.info(
                "Auto-prefetched rag document %s (%s) — %d chars injected into context",
                _doc_id_str, _filename, len(_full_content),
            )

    # ── LLM call loop (handles multi-step tool use) ───────────────────────────
    full_response_text = ""
    total_usage: dict = {}
    assistant_msg_id: int | None = None

    try:
        for _turn in range(25):  # max 25 tool-use rounds per user message
            tool_calls_received = []
            turn_text = ""

            try:
                async for event in chat_stream(
                    conn=llm_connection,
                    messages=messages,
                    tools=tools if tools else None,
                    system_prompt=system_prompt,
                    agent_id=agent.id,
                    session_id=session_id,
                    workspace_id=workspace_id,
                ):
                    match event["type"]:
                        case "text":
                            turn_text += event["delta"]
                            full_response_text += event["delta"]
                            yield _tag_event(event, agent, 0)

                        case "tool_use":
                            tool_calls_received.extend(event["tool_calls"])

                        case "done":
                            total_usage = event.get("usage", {})
            except ValueError as exc:
                if "Cannot decrypt stored secret" in str(exc):
                    err_msg = (
                        f"Cannot decrypt LLM connection '{llm_connection.name}'. "
                        "Re-enter its API key or restore the original CATALOG_ENCRYPTION_KEY."
                    )
                    yield {"type": "error", "message": err_msg}
                    return
                raise
            except Exception as exc:
                exc_type_name = type(exc).__name__
                is_conn_err = "Connection" in exc_type_name or "connect" in str(exc).lower() or "socket" in str(exc).lower()
                if is_conn_err:
                    err_msg = (
                        f"Connection error reaching LLM connection '{llm_connection.name}' ({llm_connection.provider}). "
                        "Please check network connectivity, endpoint base URL, or API key configuration."
                    )
                    logger.error("LLM connection error in orchestrator: %s", exc)
                    yield {"type": "error", "message": err_msg}
                    return
                raise

            # Persist text generated in this turn before executing tools
            if not sandbox and turn_text.strip():
                turn_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.assistant,
                    content=turn_text,
                    agent_name=agent.name,
                    agent_color=agent.color,
                    invocation_depth=0,
                )
                db.add(turn_msg)
                db.commit()

            if not tool_calls_received:
                break

            # ── Execute tool calls ────────────────────────────────────────────────
            messages.append({
                "role": "assistant",
                "content": turn_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                        **({"thought_signature": tc["thought_signature"]} if tc.get("thought_signature") else {}),
                    }
                    for tc in tool_calls_received
                ],
            })

            for tc in tool_calls_received:
                yield {"type": "tool_start", "tool_name": tc["name"], "args": tc["arguments"]}

                skill_result = await execute_tool(
                    tool_key=tc["name"],
                    arguments=tc["arguments"],
                    agent=agent,
                    db=db,
                    extra_tools=extra_tools,
                    runtime_context=runtime_context,
                )

                result_payload = skill_result.get("result", {})
                error_payload = skill_result.get("error")
                ok = skill_result["ok"]

                yield {
                    "type": "tool_end",
                    "tool_name": tc["name"],
                    "args": tc["arguments"],
                    "result": result_payload,
                    "error": error_payload,
                    "ok": ok,
                    "duration_ms": skill_result.get("duration_ms"),
                }

                # ── G1: Register asset references from this tool result ─────────────────
                _active_plan_id = active_plan.plan_id if active_plan else None
                try:
                    register_from_tool_result(
                        session_id=session_id,
                        tool_name=tc["name"],
                        result=result_payload if isinstance(result_payload, dict) else {},
                        plan_id=_active_plan_id,
                    )
                except Exception as _reg_err:
                    logger.debug("Asset registry update failed (non-fatal): %s", _reg_err)

                # ── G5: Capture before/after change record if tool edited/created an asset ──────
                if ok and isinstance(result_payload, dict):
                    try:
                        args = tc.get("arguments", {})
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except Exception: args = {}
                        if not isinstance(args, dict): args = {}

                        ctx = args.get("context") if isinstance(args.get("context"), dict) else {}
                        pld = args.get("payload") if isinstance(args.get("payload"), dict) else {}
                        res_data = result_payload.get("data") if isinstance(result_payload.get("data"), dict) else {}

                        fn = (
                            result_payload.get("full_name") or
                            args.get("full_name") or
                            ctx.get("path") or
                            ctx.get("notebook_path") or
                            pld.get("notebook_path") or
                            pld.get("full_name") or
                            args.get("path")
                        )
                        if not fn:
                            cat = result_payload.get("catalog_name") or args.get("catalog_name") or pld.get("catalog_name")
                            sch = result_payload.get("schema_name") or args.get("schema_name") or pld.get("schema_name")
                            nm = result_payload.get("notebook_name") or result_payload.get("name") or args.get("notebook_name") or args.get("name") or pld.get("notebook_name")
                            if cat and sch and nm:
                                fn = f"{cat}.{sch}.{nm}"

                        ot = result_payload.get("object_type") or args.get("object_type") or ("notebook" if "notebook" in tc["name"].lower() else "table")
                        before = result_payload.get("before_content") or args.get("before_content")

                        after = (
                            result_payload.get("after_content") or
                            result_payload.get("content") or
                            result_payload.get("code") or
                            args.get("content") or
                            args.get("code") or
                            args.get("query")
                        )
                        if not after:
                            cells = pld.get("cells") or res_data.get("cells")
                            if isinstance(cells, list):
                                c_texts = [c.get("code") or c.get("source") for c in cells if isinstance(c, dict) and (c.get("code") or c.get("source"))]
                                if c_texts: after = "\n\n".join(c_texts)
                            elif "comment" in args:
                                after = f"# Notebook/Asset created\n# Comment: {args['comment']}"

                        if fn and after and isinstance(fn, str) and isinstance(after, str):
                            curr_step = None
                            if active_plan:
                                for st in active_plan.steps:
                                    if st.status == "in_progress":
                                        curr_step = st.id
                                        break
                            from app.agents.services.agent.change_capture_service import capture_change
                            capture_change(
                                db=db,
                                session_id=session_id,
                                full_name=fn,
                                object_type=str(ot),
                                before=before if isinstance(before, str) else None,
                                after=after,
                                step_id=curr_step,
                                plan_id=_active_plan_id,
                            )
                    except Exception as _cap_err:
                        logger.debug("Change capture failed (non-fatal): %s", _cap_err)

                if not sandbox:
                    tool_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.tool,
                        content=None,
                        tool_name=tc["name"],
                        tool_result={
                            "args": tc["arguments"],
                            "result": result_payload,
                            "error": error_payload,
                            "ok": ok,
                            "duration_ms": skill_result.get("duration_ms"),
                        },
                        agent_name=agent.name,
                        invocation_depth=0,
                    )
                    db.add(tool_msg)

                tool_content = json.dumps(result_payload if ok else {"error": error_payload})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_content,
                })

            if not sandbox:
                db.commit()
    except Exception as exc:
        logger.exception("Error in agent orchestrator execution loop: %s", exc)
        err_text = f"\n\n> ⚠️ **Agent Error**: {str(exc)}"
        yield _tag_event({"type": "text", "delta": err_text}, agent, 0)
        yield {"type": "error", "message": str(exc)}
        if not sandbox:
            err_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.assistant,
                content=err_text,
                agent_name=agent.name,
                agent_color=agent.color,
                invocation_depth=0,
            )
            db.add(err_msg)
            db.commit()
        return

    # ── Guard: max tool-use rounds exceeded with no final text ────────────────
    if not full_response_text and tool_calls_received:
        full_response_text = "_(Agent reached maximum tool-use steps without producing a final response.)_"
        yield _tag_event({"type": "text", "delta": full_response_text}, agent, 0)
        if not sandbox:
            asst_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.assistant,
                content=full_response_text,
                tokens_used=total_usage.get("output_tokens"),
                agent_name=agent.name,
                agent_color=agent.color,
                invocation_depth=0,
            )
            db.add(asst_msg)
            db.commit()

    # Notify Memory Activity
    if not sandbox and full_response_text:
        try:
            from app.memory import memory_orchestrator
            if memory_orchestrator:
                await memory_orchestrator.on_activity(str(session_id), user_id, workspace_id)
        except Exception as e:
            logger.error("Failed to notify activity to memory orchestrator: %s", e)

        if not session.title:
            session.title = user_content[:80]
            db.commit()

    yield {
        "type": "done",
        "usage": total_usage,
        "session_id": session_id,
        "message_id": assistant_msg_id,
    }


# ── Subagent orchestrator ─────────────────────────────────────────────────────

async def orchestrate_subagent_stream(
    session_id: int,
    initial_prompt: str,
    subagent_id: int,
    invocation_depth: int,
    db: Session,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> AsyncIterator[dict]:
    """
    Run a subagent turn inside an *existing* ChatSession.

    This is the equivalent of run_subagent() from the architecture spec,
    adapted to the function-based orchestrator pattern.

    Args:
        session_id:        Existing ChatSession.id — subagent joins this session.
        initial_prompt:    Built by InvokeAgentTool; includes history + task.
        subagent_id:       Agent.id of the subagent to invoke.
        invocation_depth:  Parent depth + 1. Max 3.
        db:                SQLAlchemy session.

    Yields dicts tagged with agent_id, agent_name, agent_color, invocation_depth.
    Does NOT create a new ChatSession.
    """
    # ── Load subagent ─────────────────────────────────────────────────────────
    subagent = _load_agent(db, subagent_id)
    if not subagent:
        yield {"type": "error", "message": f"Subagent {subagent_id} not found"}
        return

    if not subagent.llm_connection:
        yield {
            "type": "error",
            "message": f"Subagent '{subagent.name}' has no LLM connection configured",
        }
        return

    # ── Verify session exists (we join it, never create) ─────────────────────
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        yield {"type": "error", "message": "Session not found for subagent"}
        return

    # ── Build system prompt ───────────────────────────────────────────────────
    system_prompt = build_system_prompt(db, subagent)
    subagent_llm_conn = _resolve_llm_connection(db, subagent)

    # ── Subagent only sees the initial_prompt as its user turn ───────────────
    # (History was injected into the prompt by InvokeAgentTool.)
    messages = [{"role": "user", "content": initial_prompt}]

    # ── Tool setup ──────────────────────────────────────────────────
    enabled_tool_keys = [t.tool_name for t in subagent.tools]
    # Auto-inject skills tools if subagent has skills attached
    if subagent.skills:
        if "list_available_skills" not in enabled_tool_keys:
            enabled_tool_keys.append("list_available_skills")
        if "read_skill" not in enabled_tool_keys:
            enabled_tool_keys.append("read_skill")

    tools = get_tool_definitions(enabled_tool_keys)

    loop = asyncio.get_event_loop()
    extra_tools = _build_extra_tools(
        agent=subagent,
        enabled_tool_keys=enabled_tool_keys,
        session_id=session_id,
        invocation_depth=invocation_depth,
        db=db,
        loop=loop,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    extra_keys = set(extra_tools.keys())
    tools = [t for t in tools if t["function"]["name"] not in extra_keys]
    for et in extra_tools.values():
        tools.append(et.to_openai_definition())

    # ── LLM call loop ─────────────────────────────────────────────────────────
    full_response_text = ""
    total_usage: dict = {}

    for _turn in range(5):
        tool_calls_received = []
        turn_text = ""

        async for event in chat_stream(
            conn=subagent_llm_conn,
            messages=messages,
            tools=tools if tools else None,
            system_prompt=system_prompt,
            agent_id=subagent.id,
            session_id=session_id,
            workspace_id=workspace_id,
        ):
            match event["type"]:
                case "text":
                    turn_text += event["delta"]
                    full_response_text += event["delta"]
                    yield _tag_event(event, subagent, invocation_depth)

                case "tool_use":
                    tool_calls_received.extend(event["tool_calls"])

                case "done":
                    total_usage = event.get("usage", {})

        if turn_text.strip():
            turn_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.assistant,
                content=turn_text,
                agent_name=subagent.name,
                agent_color=subagent.color,
                invocation_depth=invocation_depth,
            )
            db.add(turn_msg)
            db.commit()

        if not tool_calls_received:
            break

        messages.append({
            "role": "assistant",
            "content": turn_text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                }
                for tc in tool_calls_received
            ],
        })

        for tc in tool_calls_received:
            yield _tag_event(
                {"type": "tool_start", "tool_name": tc["name"], "args": tc["arguments"]},
                subagent,
                invocation_depth,
            )

            skill_result = await execute_tool(
                tool_key=tc["name"],
                arguments=tc["arguments"],
                agent=subagent,
                db=db,
                extra_tools=extra_tools,
            )

            result_payload = skill_result.get("result", {})
            error_payload = skill_result.get("error")
            ok = skill_result["ok"]

            yield _tag_event(
                {
                    "type": "tool_end",
                    "tool_name": tc["name"],
                    "args": tc["arguments"],
                    "result": result_payload,
                    "error": error_payload,
                    "ok": ok,
                    "duration_ms": skill_result.get("duration_ms"),
                },
                subagent,
                invocation_depth,
            )

            # Persist tool log
            tool_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.tool,
                content=None,
                tool_name=tc["name"],
                tool_result={
                    "args": tc["arguments"],
                    "result": result_payload,
                    "error": error_payload,
                    "ok": ok,
                    "duration_ms": skill_result.get("duration_ms"),
                },
                agent_name=subagent.name,
                agent_color=subagent.color,
                invocation_depth=invocation_depth,
            )
            db.add(tool_msg)

            tool_content = json.dumps(result_payload if ok else {"error": error_payload})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_content,
            })

        db.commit()

    # ── Guard ─────────────────────────────────────────────────────────────────
    if not full_response_text and tool_calls_received:
        full_response_text = "_(Subagent reached maximum tool-use steps without producing a final response.)_"
        yield _tag_event({"type": "text", "delta": full_response_text}, subagent, invocation_depth)
        asst_msg = ChatMessage(
            session_id=session_id,
            role=MessageRole.assistant,
            content=full_response_text,
            tokens_used=total_usage.get("output_tokens"),
            agent_name=subagent.name,
            agent_color=subagent.color,
            invocation_depth=invocation_depth,
        )
        db.add(asst_msg)
        db.commit()

    yield _tag_event(
        {
            "type": "done",
            "usage": total_usage,
            "session_id": session_id,
            "message_id": None,
        },
        subagent,
        invocation_depth,
    )

