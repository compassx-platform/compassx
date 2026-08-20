"""External Tool Execution Service — implements ephemeral execution, concurrency caps,
timeout enforcement, output truncation, structured errors, and audit logging.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.database import SystemSessionLocal, AccountSessionLocal
from app.agents.models.external_connection import ExternalConnection, ToolInvocationAuditLog
from app.catalog.models import UnifiedCatalogTool, UnifiedCatalogToolVersion
from app.agents.services.external_connection_service import get_connection, get_decrypted_auth_config

logger = logging.getLogger(__name__)

# Execution constraints per spec (D4, D6, D9)
_INVOCATION_TIMEOUT_SECONDS = 30
_MAX_RESULT_BYTES = 50 * 1024  # 50 KB
_TRUNCATION_MARKER = "\n[TRUNCATED: Result exceeded 50KB limit]"
_POOL_CONCURRENCY_CAP = 20
_CONNECTION_CONCURRENCY_CAP = 5
_QUEUE_WAIT_TIMEOUT = 2.0  # seconds to wait for available slot before returning rate_limited

# In-process concurrency semaphores (D4)
_POOL_SEMAPHORE = asyncio.Semaphore(_POOL_CONCURRENCY_CAP)
_CONNECTION_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
_SEMAPHORE_LOCK = asyncio.Lock()


async def _get_connection_semaphore(connection_id: str) -> asyncio.Semaphore:
    async with _SEMAPHORE_LOCK:
        if connection_id not in _CONNECTION_SEMAPHORES:
            _CONNECTION_SEMAPHORES[connection_id] = asyncio.Semaphore(_CONNECTION_CONCURRENCY_CAP)
        return _CONNECTION_SEMAPHORES[connection_id]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _write_audit_log(
    tool_id: Optional[str],
    tool_version_id: Optional[str],
    connection_id: Optional[str],
    session_id: Optional[str],
    agent_type: str,
    invoked_by: Optional[str],
    params: dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
    result_size_bytes: int,
    status: str,
    error_type: Optional[str],
) -> None:
    """Write an audit log row to system_db in a safe standalone transaction."""
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    try:
        with SystemSessionLocal() as sdb:
            audit_entry = ToolInvocationAuditLog(
                id=str(uuid.uuid4()),
                tool_id=str(tool_id) if tool_id else None,
                tool_version_id=str(tool_version_id) if tool_version_id else None,
                connection_id=str(connection_id) if connection_id else None,
                session_id=str(session_id) if session_id else None,
                agent_type=agent_type or "nova",
                invoked_by=invoked_by or "default_user",
                params=params,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                result_size_bytes=result_size_bytes,
                status=status,
                error_type=error_type,
            )
            sdb.add(audit_entry)
            sdb.commit()
    except Exception as exc:
        logger.warning("Failed to write tool invocation audit log: %s", exc)


def _validate_params(param_schema: dict[str, Any], params: dict[str, Any]) -> Optional[str]:
    """Validate parameters against declared JSON schema. Returns error message if invalid."""
    if not isinstance(params, dict):
        return "Params must be a JSON object"
    required = param_schema.get("required", [])
    for field in required:
        if field not in params:
            return f"Missing required parameter '{field}'"
    return None


def _execute_code_in_subprocess(
    source_code: str,
    function_name: str,
    params: dict[str, Any],
    connections_config: dict[str, Any],
) -> Tuple[bool, Any, Optional[str], Optional[str]]:
    """Execute tool function in an isolated ephemeral subprocess.

    Returns (success, result, error_type, clean_error_message).
    """
    with tempfile.TemporaryDirectory(prefix="cx_tool_") as tmpdir:
        script_path = os.path.join(tmpdir, "runner.py")
        payload_path = os.path.join(tmpdir, "payload.json")

        payload_data = {
            "source_code": source_code,
            "function_name": function_name,
            "params": params,
            "connections": connections_config,
        }

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload_data, f)

        # Runner script executed inside ephemeral child process
        runner_code = textwrap.dedent("""
            import sys
            import json
            import os

            # Add backend to sys.path so services.compassx_tools and cx can be imported
            backend_dir = os.environ.get("COMPASSX_BACKEND_DIR")
            if backend_dir and backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            from services.compassx_tools import connections as cx_connections

            payload_file = sys.argv[1]
            with open(payload_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            source_code = data["source_code"]
            func_name = data["function_name"]
            params = data["params"]
            connections_cfg = data.get("connections", {})

            # Ingest active connections into cx.connections
            cx_connections.set_active_connections(connections_cfg)

            # Execute user source code in clean namespace
            namespace = {
                "__name__": "__main__",
                "connections": cx_connections,
            }
            try:
                exec(compile(source_code, "<user_tool>", "exec"), namespace)
            except Exception as e:
                output = {
                    "ok": False,
                    "error_type": "runtime_error",
                    "error": f"Error loading tool code: {type(e).__name__}: {e}",
                }
                print(json.dumps(output))
                sys.exit(0)

            target_fn = namespace.get(func_name)
            if not target_fn or not callable(target_fn):
                # Search for decorated tool function
                for k, v in namespace.items():
                    if callable(v) and getattr(v, "_is_cx_tool", False):
                        target_fn = v
                        break
                if not target_fn:
                    output = {
                        "ok": False,
                        "error_type": "invalid_params",
                        "error": f"Tool function '{func_name}' not found in source code.",
                    }
                    print(json.dumps(output))
                    sys.exit(0)

            try:
                result = target_fn(**params)
                output = {
                    "ok": True,
                    "result": result,
                }
                print(json.dumps(output))
            except Exception as e:
                err_str = str(e)
                err_type_name = type(e).__name__
                if "ConnectionUnreachable" in err_type_name or "ConnectError" in err_type_name or "NetworkError" in err_type_name:
                    err_type = "connection_unreachable"
                elif isinstance(e, TypeError) and ("unexpected keyword" in err_str or "missing" in err_str):
                    err_type = "invalid_params"
                else:
                    err_type = "runtime_error"
                output = {
                    "ok": False,
                    "error_type": err_type,
                    "error": f"{err_type_name}: {err_str}",
                }
                print(json.dumps(output))
        """)

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(runner_code)

        backend_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
        )

        sub_env = os.environ.copy()
        sub_env["COMPASSX_BACKEND_DIR"] = backend_path
        sub_env["PYTHONPATH"] = f"{backend_path}{os.pathsep}{sub_env.get('PYTHONPATH', '')}"
        sub_env["CX_CONNECTIONS_JSON"] = json.dumps(connections_config)

        try:
            proc = subprocess.run(
                [sys.executable, script_path, payload_path],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=sub_env,
                timeout=_INVOCATION_TIMEOUT_SECONDS,
            )
            stdout_text = proc.stdout.decode("utf-8", errors="replace").strip()
            stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()

            if not stdout_text:
                logger.warning("Subprocess stderr: %s", stderr_text)
                return False, None, "runtime_error", stderr_text or "Process returned no output"

            # Parse JSON output
            try:
                # Find last valid JSON line
                lines = [l for l in stdout_text.splitlines() if l.strip()]
                res_data = json.loads(lines[-1])
                if res_data.get("ok"):
                    return True, res_data.get("result"), None, None
                else:
                    return False, None, res_data.get("error_type", "runtime_error"), res_data.get("error", "Execution failed")
            except Exception as e:
                return False, None, "runtime_error", f"Malformed tool output: {stdout_text[:500]}"

        except subprocess.TimeoutExpired:
            return False, None, "timeout", f"Execution timed out after {_INVOCATION_TIMEOUT_SECONDS}s"
        except Exception as exc:
            logger.exception("Ephemeral tool execution failed: %s", exc)
            return False, None, "runtime_error", f"Tool process error: {exc}"


async def execute_agent_tool(
    tool_id: str,
    version: Optional[int] = None,
    connection_id: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
    agent_type: str = "nova",
    invoked_by: Optional[str] = None,
) -> dict[str, Any]:
    """Execute an agent tool with full safety guarantees per spec.

    Returns:
        {"ok": True, "result": Any, "truncated": bool}
        OR
        {"ok": False, "error_type": str, "message": str, "retryable": bool}
    """
    started_at = _utcnow()
    params = params or {}
    tool_version_id: Optional[str] = None
    target_source_code: str = ""
    target_func_name: str = ""
    param_schema: dict[str, Any] = {}
    declared_connections: list[str] = []

    # ── 1. Resolve Tool & Version from Catalog DB ─────────────────────────────
    with AccountSessionLocal() as adb:
        tool = adb.query(UnifiedCatalogTool).filter(UnifiedCatalogTool.id == tool_id).first()
        if not tool:
            # Check by name if ID was passed as name
            tool = adb.query(UnifiedCatalogTool).filter(UnifiedCatalogTool.name == tool_id).first()
            if not tool:
                msg = f"Tool '{tool_id}' not found in catalog."
                finished_at = _utcnow()
                _write_audit_log(
                    tool_id=None,
                    tool_version_id=None,
                    connection_id=connection_id,
                    session_id=session_id,
                    agent_type=agent_type,
                    invoked_by=invoked_by,
                    params=params,
                    started_at=started_at,
                    finished_at=finished_at,
                    result_size_bytes=0,
                    status="failure",
                    error_type="invalid_params",
                )
                return {
                    "ok": False,
                    "error_type": "invalid_params",
                    "message": msg,
                    "retryable": False,
                }

        tool_id_str = tool.id
        target_func_name = tool.name

        if version is not None:
            v_row = (
                adb.query(UnifiedCatalogToolVersion)
                .filter(
                    UnifiedCatalogToolVersion.tool_id == tool.id,
                    UnifiedCatalogToolVersion.version == version,
                )
                .first()
            )
            if not v_row:
                msg = f"Version {version} for tool '{tool.name}' not found."
                finished_at = _utcnow()
                _write_audit_log(
                    tool_id=tool_id_str,
                    tool_version_id=None,
                    connection_id=connection_id,
                    session_id=session_id,
                    agent_type=agent_type,
                    invoked_by=invoked_by,
                    params=params,
                    started_at=started_at,
                    finished_at=finished_at,
                    result_size_bytes=0,
                    status="failure",
                    error_type="invalid_params",
                )
                return {
                    "ok": False,
                    "error_type": "invalid_params",
                    "message": msg,
                    "retryable": False,
                }
            tool_version_id = v_row.id
            target_source_code = v_row.source_code
            param_schema = v_row.param_schema or {}
            declared_connections = v_row.connection_dependencies or []
        else:
            # Latest version
            tool_version_id = None
            target_source_code = tool.source_code
            param_schema = tool.param_schema or {}
            declared_connections = tool.connection_dependencies or []

    # ── 2. Parameter Validation ───────────────────────────────────────────────
    validation_err = _validate_params(param_schema, params)
    if validation_err:
        finished_at = _utcnow()
        _write_audit_log(
            tool_id=tool_id_str,
            tool_version_id=tool_version_id,
            connection_id=connection_id,
            session_id=session_id,
            agent_type=agent_type,
            invoked_by=invoked_by,
            params=params,
            started_at=started_at,
            finished_at=finished_at,
            result_size_bytes=0,
            status="failure",
            error_type="invalid_params",
        )
        return {
            "ok": False,
            "error_type": "invalid_params",
            "message": validation_err,
            "retryable": False,
        }

    # ── 3. Resolve Connections Server-Side (D5, D12, D2) ──────────────────────
    connections_config: dict[str, Any] = {}
    primary_conn_id: Optional[str] = connection_id

    with SystemSessionLocal() as sdb:
        # If connection_id explicit (D5)
        if connection_id:
            conn_obj = get_connection(sdb, connection_id)
            if not conn_obj or conn_obj.status != "active":
                msg = f"External connection '{connection_id}' is disabled or not found."
                finished_at = _utcnow()
                _write_audit_log(
                    tool_id=tool_id_str,
                    tool_version_id=tool_version_id,
                    connection_id=connection_id,
                    session_id=session_id,
                    agent_type=agent_type,
                    invoked_by=invoked_by,
                    params=params,
                    started_at=started_at,
                    finished_at=finished_at,
                    result_size_bytes=0,
                    status="failure",
                    error_type="connection_unreachable",
                )
                return {
                    "ok": False,
                    "error_type": "connection_unreachable",
                    "message": msg,
                    "retryable": False,
                }
            auth_decrypted = get_decrypted_auth_config(conn_obj)
            connections_config[conn_obj.name] = {
                "base_url": conn_obj.base_url,
                "auth_config": auth_decrypted,
                "connector_type": conn_obj.connector_type,
            }
            primary_conn_id = str(conn_obj.id)

        # Also resolve any declared connections from tool decorator (D12)
        for dep_name in declared_connections:
            if dep_name in connections_config:
                continue
            # Try by name or ID
            conn_obj = get_connection(sdb, dep_name) or sdb.query(ExternalConnection).filter(ExternalConnection.name == dep_name).first()
            if not conn_obj or conn_obj.status != "active":
                msg = f"Required external connection '{dep_name}' is disabled or not found."
                finished_at = _utcnow()
                _write_audit_log(
                    tool_id=tool_id_str,
                    tool_version_id=tool_version_id,
                    connection_id=primary_conn_id,
                    session_id=session_id,
                    agent_type=agent_type,
                    invoked_by=invoked_by,
                    params=params,
                    started_at=started_at,
                    finished_at=finished_at,
                    result_size_bytes=0,
                    status="failure",
                    error_type="connection_unreachable",
                )
                return {
                    "ok": False,
                    "error_type": "connection_unreachable",
                    "message": msg,
                    "retryable": False,
                }
            auth_decrypted = get_decrypted_auth_config(conn_obj)
            connections_config[conn_obj.name] = {
                "base_url": conn_obj.base_url,
                "auth_config": auth_decrypted,
                "connector_type": conn_obj.connector_type,
            }
            if not primary_conn_id:
                primary_conn_id = str(conn_obj.id)

    # ── 4. Concurrency Caps (D4) ──────────────────────────────────────────────
    conn_sem = await _get_connection_semaphore(primary_conn_id or "global")
    try:
        # Acquire pool semaphore with bounded timeout
        await asyncio.wait_for(_POOL_SEMAPHORE.acquire(), timeout=_QUEUE_WAIT_TIMEOUT)
    except asyncio.TimeoutError:
        finished_at = _utcnow()
        _write_audit_log(
            tool_id=tool_id_str,
            tool_version_id=tool_version_id,
            connection_id=primary_conn_id,
            session_id=session_id,
            agent_type=agent_type,
            invoked_by=invoked_by,
            params=params,
            started_at=started_at,
            finished_at=finished_at,
            result_size_bytes=0,
            status="failure",
            error_type="rate_limited",
        )
        return {
            "ok": False,
            "error_type": "rate_limited",
            "message": "Global tool execution concurrency cap reached; request rate limited.",
            "retryable": True,
        }

    try:
        # Acquire per-connection semaphore with bounded timeout
        try:
            await asyncio.wait_for(conn_sem.acquire(), timeout=_QUEUE_WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            _POOL_SEMAPHORE.release()
            finished_at = _utcnow()
            _write_audit_log(
                tool_id=tool_id_str,
                tool_version_id=tool_version_id,
                connection_id=primary_conn_id,
                session_id=session_id,
                agent_type=agent_type,
                invoked_by=invoked_by,
                params=params,
                started_at=started_at,
                finished_at=finished_at,
                result_size_bytes=0,
                status="failure",
                error_type="rate_limited",
            )
            return {
                "ok": False,
                "error_type": "rate_limited",
                "message": f"Connection concurrency cap reached for '{primary_conn_id}'; request rate limited.",
                "retryable": True,
            }

        # ── 5. Ephemeral Subprocess Dispatch (D8, D7, D9) ─────────────────────
        try:
            loop = asyncio.get_event_loop()
            success, raw_result, err_type, err_msg = await loop.run_in_executor(
                None,
                _execute_code_in_subprocess,
                target_source_code,
                target_func_name,
                params,
                connections_config,
            )
        finally:
            conn_sem.release()
            _POOL_SEMAPHORE.release()

    except Exception as e:
        finished_at = _utcnow()
        _write_audit_log(
            tool_id=tool_id_str,
            tool_version_id=tool_version_id,
            connection_id=primary_conn_id,
            session_id=session_id,
            agent_type=agent_type,
            invoked_by=invoked_by,
            params=params,
            started_at=started_at,
            finished_at=finished_at,
            result_size_bytes=0,
            status="failure",
            error_type="runtime_error",
        )
        return {
            "ok": False,
            "error_type": "runtime_error",
            "message": str(e),
            "retryable": False,
        }

    finished_at = _utcnow()

    # ── 6. Handle Outcome & Truncation (D6, D9) ──────────────────────────────
    if not success:
        _write_audit_log(
            tool_id=tool_id_str,
            tool_version_id=tool_version_id,
            connection_id=primary_conn_id,
            session_id=session_id,
            agent_type=agent_type,
            invoked_by=invoked_by,
            params=params,
            started_at=started_at,
            finished_at=finished_at,
            result_size_bytes=0,
            status="failure",
            error_type=err_type,
        )
        retryable = err_type in ("timeout", "rate_limited")
        return {
            "ok": False,
            "error_type": err_type,
            "message": err_msg or "Tool execution error",
            "retryable": retryable,
        }

    # Serialization and truncation
    try:
        if isinstance(raw_result, str):
            serialized_str = raw_result
        else:
            serialized_str = json.dumps(raw_result)
    except Exception:
        serialized_str = str(raw_result)

    result_bytes = len(serialized_str.encode("utf-8", errors="replace"))
    truncated = False

    if result_bytes > _MAX_RESULT_BYTES:
        truncated = True
        truncated_str = serialized_str.encode("utf-8")[:_MAX_RESULT_BYTES].decode("utf-8", errors="replace")
        final_result = truncated_str + _TRUNCATION_MARKER
        result_size_for_log = len(final_result.encode("utf-8"))
    else:
        final_result = raw_result
        result_size_for_log = result_bytes

    # ── 7. Audit Log (Success) ────────────────────────────────────────────────
    _write_audit_log(
        tool_id=tool_id_str,
        tool_version_id=tool_version_id,
        connection_id=primary_conn_id,
        session_id=session_id,
        agent_type=agent_type,
        invoked_by=invoked_by,
        params=params,
        started_at=started_at,
        finished_at=finished_at,
        result_size_bytes=result_size_for_log,
        status="success",
        error_type=None,
    )

    return {
        "ok": True,
        "result": final_result,
        "truncated": truncated,
    }
