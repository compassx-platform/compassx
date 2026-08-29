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
import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy.orm import Session, selectinload

from app.models.agents import (
    Agent,
    AgentTool,
    ChatMessage,
    ChatSession,
    LLMConnection,
    MessageRole,
)
from app.agents.services.agent.context_builder import build_agent_system_prompt, build_system_prompt
from app.services.llm_client import chat_stream
from app.agents.services.agent.tool_executor import execute_tool
from app.asset_manager.schemas.agent_context import AssetManagerContextRequest
from app.asset_manager.services.agent_context_resolver import AssetManagerContextResolver
from app.agents.schemas.agent_manifest import AgentManifest, BaseProfile
from app.agents.services.agent.request_router import RequestRouter
from app.agents.services.agent.write_gating_middleware import WriteGatingMiddleware, WriteGatingViolation
from app.agents.services.agent.plan_service import PlanService
from app.agents.services.agent.known_assets_registry import registry as _asset_registry, register_from_tool_result
from app.agents.services.agent.tools.registry import get_tool_definitions

from app.agents.services.agent.compactor import (
    DEFAULT_HIGH_WATERMARK_RATIO,
    DEFAULT_LOW_WATERMARK_K,
    ConversationTurn,
    compact_session_history,
    group_messages_into_turns,
    partition_turns_for_compaction,
    preflight_watermark_check,
)

logger = logging.getLogger(__name__)


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
            selectinload(Agent.skills),
        )
        .filter(Agent.id == agent_id)
        .first()
    )


def _get_safe_event_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop_policy().get_event_loop()


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

    if "create_plan" in enabled_tool_keys:
        from app.agents.services.agent.tools.plan_tools import CreatePlanTool

        extra["create_plan"] = CreatePlanTool(
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
        if isinstance(override_llm_connection_id, (int, str)):
            conn = (
                sys_db.query(LLMConnection)
                .filter(LLMConnection.id == override_llm_connection_id)
                .first()
            )
            if conn:
                sys_db.expunge(conn)
                return conn

        agent_conn_id = getattr(agent, "llm_connection_id", None)
        if isinstance(agent_conn_id, (int, str)):
            conn = (
                sys_db.query(LLMConnection)
                .filter(LLMConnection.id == agent_conn_id)
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

        # Fallback to direct agent.llm_connection attribute if present
        direct_conn = getattr(agent, "llm_connection", None)
        if direct_conn:
            return direct_conn
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

    # ── Manual Compaction Command Trigger (Spec D9) ───────────────────────────
    is_manual_compact = user_content.strip().lower() in ("/compact", "/compact now", "/compact_history")
    if is_manual_compact:
        assistant_msg_id = None
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

        new_summary, retained_turns = await compact_session_history(
            session=session,
            db=db,
            conn=llm_connection,
            keep_last_k=DEFAULT_LOW_WATERMARK_K,
            agent_id=agent.id,
            workspace_id=workspace_id,
        )

        confirmation_text = (
            "🧹 **Conversation Context Compacted**\n\n"
            f"Retained the latest {len(retained_turns)} turns in full detail and distilled earlier turns into the session summary.\n\n"
            f"{new_summary or '*(No earlier turns to summarize)*'}"
        )
        yield _tag_event({"type": "text", "delta": confirmation_text}, agent, 0)

        if not sandbox:
            asst_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.assistant,
                content=confirmation_text,
                agent_name=agent.name,
                agent_color=agent.color,
                invocation_depth=0,
            )
            db.add(asst_msg)
            db.commit()
            assistant_msg_id = asst_msg.id

        yield {
            "type": "done",
            "usage": {},
            "session_id": session_id,
            "message_id": assistant_msg_id,
        }
        return

    # ── Build system prompt (3-Tier Layered Architecture) ─────────────────────
    runtime_context = _resolve_runtime_context(context)
    prompt_res = build_agent_system_prompt(
        db=db,
        agent=agent,
        session_id=session_id,
        runtime_context=runtime_context,
    )
    system_prompt = prompt_res.system_prompt
    has_attachment_tool_fetch = prompt_res.has_attachment_tool_fetch

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

    # ── Resolve attached images for multimodal vision in current user turn ──
    image_parts = []
    try:
        from app.nova.services.attachment_service import STORAGE_BASE_DIR
        from app.models.agents import NovaAttachment, RagDocument
        # 1. RagDocuments
        rag_docs = db.query(RagDocument).filter(RagDocument.session_id == session_id).all()
        for rdoc in rag_docs:
            ext = (rdoc.filename or "").rsplit(".", 1)[-1].lower() if "." in (rdoc.filename or "") else ""
            is_img = (rdoc.mime_type and rdoc.mime_type.startswith("image/")) or ext in ("png", "jpg", "jpeg", "webp", "gif", "svg")
            if is_img:
                doc_dir = os.path.join(STORAGE_BASE_DIR, "sessions", str(session_id), "rag_docs", str(rdoc.id))
                img_file_path = os.path.join(doc_dir, rdoc.filename or "file")
                if os.path.exists(img_file_path):
                    with open(img_file_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    mime = rdoc.mime_type or f"image/{ext or 'png'}"
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}
                    })

        # 2. NovaAttachments
        nova_atts = db.query(NovaAttachment).filter(NovaAttachment.session_id == session_id, NovaAttachment.status == "ready").all()
        for n_att in nova_atts:
            if n_att.delivery_mode == "multimodal_native" and os.path.exists(n_att.blob_path):
                with open(n_att.blob_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{n_att.mime_type or 'image/png'};base64,{b64}"}
                })
    except Exception as img_err:
        logger.warning("Failed to collect image attachments for session %s: %s", session_id, img_err)

    if image_parts:
        user_message_payload = [{"type": "text", "text": user_content}] + image_parts
    else:
        user_message_payload = user_content

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

    # Auto-set approved_at on plan if user message expresses approval intent
    approval_pattern = re.compile(
        r"^(i\s+)?(approve|approved|proceed|go\s+ahead|yes(,\s*|\s+)approve|looks\s+good|start\s+execution)",
        re.IGNORECASE,
    )
    if approval_pattern.search(user_content.strip()):
        from app.agents.services.agent.plan_service import PlanService
        _plan_svc = PlanService()
        for _p in _plan_svc.get_plans_for_session(session_id):
            if not _p.approved_at:
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
            f"   b. If get_next_step indicates blocked=True or completed=True, STOP immediately.\n"
            f"   c. Call mark_step(..., step_id=<id>, status='in_progress').\n"
            f"   d. Perform the ACTUAL work for that step. When creating notebooks or assets, use the registered catalogs (e.g. 'main', 'sandbox') and pass complete code into notebook_manager(operation='create_notebook', payload={{'catalog_name': '...', 'schema_name': '...', 'notebook_name': '...', 'code': '...'}}). Always execute the notebook cells using notebook_manager(operation='run_cell', payload={{'run_all': True}}) or specific cell_index / cell_indices to test and persist cell outputs.\n"
            f"   e. If tool execution encounters an error, DO NOT mark it 'done' and DO NOT skip to the next step! Either fix the error and retry that same step until successful, or record the failure and halt.\n"
            f"   f. Call mark_step(..., step_id=<id>, status='done', result={{...}}).\n"
            f"   g. IMMEDIATELY continue to the next step.\n"
            f"3. STOP when get_next_step returns completed=True or blocked=True.\n"
            f"4. Do NOT create a new plan. Do NOT ask for user approval again. START EXECUTING NOW.\n"
            f"\nFirst step to execute: {step_desc}\n"
        )
        system_prompt += plan_directive
    # Always ensure planning & building tools are available for all session turns
    for plan_tool_name in ["create_plan", "get_plan", "get_next_step", "mark_step", "append_correction", "escalate_to_plan"]:
        if plan_tool_name not in enabled_tool_keys:
            enabled_tool_keys.append(plan_tool_name)
    for build_tool_name in ["notebook_manager", "python_code", "sql_warehouse", "asset_manager"]:
        if build_tool_name not in enabled_tool_keys:
            enabled_tool_keys.append(build_tool_name)

    from app.agents.services.agent.tools.registry import get_tool_definitions
    tools = get_tool_definitions(enabled_tool_keys)

    # ── Per-request stateful tools (e.g. InvokeAgentTool) ────────────────────
    loop = _get_safe_event_loop()
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
    extra_keys = set(extra_tools.keys())
    tools = [t for t in tools if t["function"]["name"] not in extra_keys]
    for et in extra_tools.values():
        tools.append(et.to_openai_definition())

    # ── Auto-Prefetch Attachments (Server-Side) ─────────────────────────────
    prefetched_messages: list[dict[str, Any]] = []
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

            _call_id = f"prefetch_{_file_id_str[:8]}"
            _MAX_PREFETCH_CHARS = 80_000
            if len(_full_content) > _MAX_PREFETCH_CHARS:
                _full_content = (
                    _full_content[:_MAX_PREFETCH_CHARS]
                    + f"\n\n[... Document truncated at {_MAX_PREFETCH_CHARS} chars for context limits. "
                    f"Use fetch_attachment(file_id='{_file_id_str}', page=N) to read specific pages ...]"
                )

            prefetched_messages.append({
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
            prefetched_messages.append({
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

            prefetched_messages.append({
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
            prefetched_messages.append({
                "role": "tool",
                "tool_call_id": _call_id,
                "name": "fetch_attachment",
                "content": _full_content,
            })
            logger.info(
                "Auto-prefetched rag document %s (%s) — %d chars injected into context",
                _doc_id_str, _filename, len(_full_content),
            )

    # ── Watermark Compaction Pre-Flight Check (Spec D1, D2, D8, D10) ──────────
    active_summary, retained_turns, did_compact = await preflight_watermark_check(
        session=session,
        db=db,
        conn=llm_connection,
        system_prompt=system_prompt,
        prefetched_messages=prefetched_messages,
        current_user_content=user_content,
        keep_last_k=DEFAULT_LOW_WATERMARK_K,
        high_watermark_ratio=DEFAULT_HIGH_WATERMARK_RATIO,
        agent_id=agent.id,
        workspace_id=workspace_id,
    )

    if active_summary and active_summary.strip():
        system_prompt += (
            f"\n\n---\n\n## SUMMARY OF EARLIER CONVERSATION HISTORY (Turns prior to active window)\n"
            f"{active_summary.strip()}\n"
            f"---\n"
        )

    # Assemble messages payload with retained full raw turns + attachments + current user msg
    messages: list[dict[str, Any]] = []
    for t in retained_turns:
        messages.extend(t.to_llm_messages())

    messages.extend(prefetched_messages)
    messages.append({"role": "user", "content": user_message_payload, "id": user_msg_id})

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
                captured_change_info = None
                if ok and isinstance(result_payload, dict):
                    try:
                        args = tc.get("arguments", {})
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except Exception: args = {}
                        if not isinstance(args, dict): args = {}

                        curr_step = None
                        if active_plan:
                            for st in active_plan.steps:
                                if st.status in ("in_progress", "done"):
                                    curr_step = st.id
                                    break

                        from app.agents.services.agent.change_capture import capture_tool_change
                        captured_change_info = capture_tool_change(
                            db=db,
                            session_id=session_id,
                            tool_name=tc["name"],
                            arguments=args,
                            result_payload=result_payload if isinstance(result_payload, dict) else {},
                            step_id=curr_step or (args.get("step_id") if isinstance(args.get("step_id"), int) else None),
                            plan_id=_active_plan_id,
                            goal=active_plan.goal if active_plan else None,
                            context=tc.get("context"),
                        )
                    except Exception as _cap_err:
                        logger.warning("Change capture failed (non-fatal): %s", _cap_err)

                if not sandbox:
                    tool_res_dict = {
                        "args": tc["arguments"],
                        "result": result_payload,
                        "error": error_payload,
                        "ok": ok,
                        "duration_ms": skill_result.get("duration_ms"),
                    }
                    if captured_change_info:
                        tool_res_dict["change"] = captured_change_info

                    tool_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.tool,
                        content=None,
                        tool_name=tc["name"],
                        tool_result=tool_res_dict,
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

        if not session.title:
            session.title = user_content[:80]
            db.commit()

        # Reconcile plan steps to completed if agent delivered its final response cleanly
        if active_plan and full_response_text and not full_response_text.startswith("_(Agent reached maximum"):
            try:
                from app.agents.services.agent.plan_service import PlanService, StepStatus
                ps = PlanService()
                cur_p = ps.get_plan(active_plan.plan_id)
                if cur_p and any(s.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS) for s in cur_p.steps):
                    for st in cur_p.steps:
                        if st.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
                            ps.mark_step(cur_p.plan_id, st.id, StepStatus.DONE, result={"auto_completed": True})
            except Exception as _sync_err:
                logger.debug("Plan step reconciliation skipped: %s", _sync_err)

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

    loop = _get_safe_event_loop()
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

