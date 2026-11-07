"""Runtime configuration loaded from the sandbox environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NovaSettings:
    session_id: str
    workspace_root: str
    state_dir: str
    model: str
    gateway_url: str
    gateway_key: str
    platform_url: str
    workspace_id: str
    max_turns: int = 24
    tool_timeout_s: int = 30

    @classmethod
    def from_env(cls, session_id: str | None = None) -> "NovaSettings":
        sid = (session_id or os.environ.get("NOVA_SESSION_ID") or "").strip()
        if not sid:
            raise ValueError("NOVA_SESSION_ID is required.")
        root = os.environ.get("NOVA_WORKSPACE", "/workspace")
        state = os.environ.get("NOVA_STATE_DIR", f"/var/lib/compassx/nova/{sid}")
        gateway = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
        platform = (os.environ.get("COMPASSX_API_URL") or "").rstrip("/")
        if gateway.endswith("/chat/completions"):
            gateway = gateway[: -len("/chat/completions")]
        return cls(
            session_id=sid,
            workspace_root=root,
            state_dir=state,
            model=(os.environ.get("NOVA_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-5.4-mini").strip(),
            gateway_url=gateway,
            gateway_key=os.environ.get("OPENAI_API_KEY") or "",
            platform_url=platform,
            workspace_id=(os.environ.get("COMPASSX_WORKSPACE_ID") or "").strip(),
            max_turns=int(os.environ.get("NOVA_MAX_TURNS") or 24),
            tool_timeout_s=int(os.environ.get("NOVA_TOOL_TIMEOUT") or 30),
        )

    @property
    def inbox_dir(self) -> str:
        return os.path.join(self.state_dir, "inbox")

    @property
    def transcript_path(self) -> str:
        return os.path.join(self.state_dir, "transcript.jsonl")

    @property
    def chat_completions_url(self) -> str:
        return f"{self.gateway_url}/chat/completions"
