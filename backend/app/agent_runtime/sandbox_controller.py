"""Host-side controller for the in-sandbox Nova CLI.

This class only prepares, delivers, and syncs the sandbox Nova process.
The LLM loop and local tools stay in the sandbox image.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import tarfile
from pathlib import Path
from typing import Callable, Protocol

from app.sandbox.agent_cli import detached_start_command
from app.sandbox.models import ExecResult

logger = logging.getLogger(__name__)

ExecFn = Callable[..., ExecResult]
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "sandbox_nova"


class RuntimeSession(Protocol):
    id: str
    sandbox_id: str
    workspace_id: str | None
    llm_model: str | None


class NovaSandboxController:
    """Start Nova in the bound sandbox and exchange turns via inbox + transcript."""

    def prepare(self, session: RuntimeSession, exec_fn: ExecFn, llm_model: str | None = None) -> None:
        self._ensure_package(session.sandbox_id, exec_fn)
        env = self._runtime_env(session, llm_model)
        self._write_env_file(session.sandbox_id, exec_fn, env)
        self._ensure_nova_process(session, exec_fn)
        exec_fn(session.sandbox_id, f"mkdir -p /var/lib/compassx/nova/{session.id}/inbox", timeout=10)

    def _ensure_nova_process(self, session: RuntimeSession, exec_fn: ExecFn) -> None:
        probe = exec_fn(
            session.sandbox_id,
            f"ps -eo args 2>/dev/null | grep -E 'sandbox_nova serve|nova serve' | grep -F {session.id} | grep -v grep || true",
            timeout=10,
        )
        if session.id in (probe.stdout or "") and ("serve" in (probe.stdout or "")):
            return
        name = f"cx_{session.id.replace('-', '_')}"
        exec_fn(session.sandbox_id, f"tmux kill-session -t {name} 2>/dev/null || true", timeout=10)
        result = exec_fn(session.sandbox_id, detached_start_command("nova", session.id, "/workspace"), timeout=30)
        if not result.success:
            detail = (result.stderr or result.stdout or "Failed to start Nova in the sandbox.").strip()
            raise RuntimeError(detail[:500])

    def deliver(self, session: RuntimeSession, prompt: str, exec_fn: ExecFn, llm_model: str | None = None) -> None:
        self.prepare(session, exec_fn, llm_model)
        payload = json.dumps({"prompt": prompt, "model": (llm_model or session.llm_model or "").strip()})
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        command = (
            f"mkdir -p /var/lib/compassx/nova/{session.id}/inbox && "
            f"python3 -c \"import base64,time,pathlib; "
            f"d=pathlib.Path('/var/lib/compassx/nova/{session.id}/inbox'); d.mkdir(parents=True, exist_ok=True); "
            f"(d / (str(int(time.time()*1000)) + '.json')).write_bytes(base64.b64decode('{encoded}'))\""
        )
        result = exec_fn(session.sandbox_id, command, timeout=20)
        if not result.success:
            detail = (result.stderr or result.stdout or "Failed to deliver the Nova prompt.").strip()
            raise RuntimeError(detail[:500])

    def read_activities(self, session: RuntimeSession, exec_fn: ExecFn) -> list[dict]:
        command = (
            f"PYTHONPATH=/opt/compassx:${{PYTHONPATH:-}} nova transcript --session {session.id} 2>/dev/null || "
            f"PYTHONPATH=/opt/compassx python3 -m sandbox_nova transcript --session {session.id}"
        )
        result = exec_fn(session.sandbox_id, command, timeout=20)
        if not (result.stdout or "").strip():
            return []
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            return [item for item in (payload.get("activities") or []) if isinstance(item, dict)]
        return payload if isinstance(payload, list) else []

    def _runtime_env(self, session: RuntimeSession, llm_model: str | None) -> dict[str, str]:
        from app.services.sandbox_credentials import gateway_base_url, get_or_create_workspace_gateway_token

        gateway = gateway_base_url()
        platform = gateway.split("/ai-gateway")[0] if "/ai-gateway" in gateway else gateway.rsplit("/", 1)[0]
        token = ""
        workspace_id = (session.workspace_id or "").strip()
        if workspace_id:
            try:
                token = get_or_create_workspace_gateway_token(workspace_id)
            except Exception:
                logger.warning("Workspace gateway token unavailable for Nova sandbox", exc_info=True)
        return {
            "NOVA_SESSION_ID": session.id,
            "NOVA_MODEL": (llm_model or session.llm_model or "").strip(),
            "NOVA_WORKSPACE": "/workspace",
            "OPENAI_BASE_URL": gateway,
            "OPENAI_API_KEY": token,
            "COMPASSX_API_URL": platform,
            "COMPASSX_WORKSPACE_ID": workspace_id,
        }

    def _write_env_file(self, sandbox_id: str, exec_fn: ExecFn, env: dict[str, str]) -> None:
        command = (
            "python3 -c \"import os, pathlib; "
            "pathlib.Path('/run/compassx').mkdir(parents=True, exist_ok=True); "
            "keys=['NOVA_SESSION_ID','NOVA_MODEL','NOVA_WORKSPACE','OPENAI_BASE_URL','OPENAI_API_KEY','COMPASSX_API_URL','COMPASSX_WORKSPACE_ID']; "
            "lines=[k+'='+os.environ.get(k,'') for k in keys if os.environ.get(k)]; "
            "pathlib.Path('/run/compassx/nova.env').write_text(chr(10).join(lines)+chr(10)); "
            "os.chmod('/run/compassx/nova.env', 0o600)\""
        )
        result = exec_fn(sandbox_id, command, timeout=15, env=env)
        if not result.success:
            logger.warning("Failed to write Nova env file: %s", (result.stderr or result.stdout or "")[:200])

    def _ensure_package(self, sandbox_id: str, exec_fn: ExecFn) -> None:
        probe = exec_fn(
            sandbox_id,
            "command -v nova >/dev/null 2>&1 || test -d /opt/compassx/sandbox_nova && echo ok",
            timeout=10,
        )
        if probe.success and "ok" in (probe.stdout or ""):
            return
        if not PACKAGE_ROOT.is_dir():
            logger.warning("sandbox_nova package is missing on the host")
            return
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(PACKAGE_ROOT, arcname="sandbox_nova")
        blob = base64.b64encode(buffer.getvalue()).decode("ascii")
        command = (
            "python3 -c '"
            "import base64,io,os,tarfile,pathlib;"
            "pathlib.Path(\"/opt/compassx\").mkdir(parents=True, exist_ok=True);"
            "tarfile.open(fileobj=io.BytesIO(base64.b64decode(os.environ[\"NOVA_PKG\"])), mode=\"r:gz\").extractall(\"/opt/compassx\");"
            "p=pathlib.Path(\"/usr/local/bin/nova\");"
            "p.write_text(\"#!/bin/sh\\nexport PYTHONPATH=/opt/compassx:${PYTHONPATH:-}\\nexec python3 -m sandbox_nova \\\"$@\\\"\\n\");"
            "os.chmod(p, 0o755); print(\"ok\")"
            "'"
        )
        result = exec_fn(sandbox_id, command, timeout=30, env={"NOVA_PKG": blob})
        if not result.success or "ok" not in (result.stdout or ""):
            detail = (result.stderr or result.stdout or "Failed to install Nova CLI into the sandbox.").strip()
            raise RuntimeError(detail[:500])


nova_sandbox_controller = NovaSandboxController()
