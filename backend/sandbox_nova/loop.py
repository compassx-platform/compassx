"""Nova agent loop: LLM + tools + transcript. Independent of CompassX host process."""

from __future__ import annotations

import json
from typing import Any

from sandbox_nova.config import NovaSettings
from sandbox_nova.llm import GatewayLLM
from sandbox_nova.prompt import SYSTEM_PROMPT
from sandbox_nova.tools.registry import ToolRegistry
from sandbox_nova.transcript import TranscriptStore

from sandbox_nova.inbox import InboxServer


class NovaAgentLoop:
    def __init__(self, settings: NovaSettings, llm: GatewayLLM, tools: ToolRegistry, transcript: TranscriptStore) -> None:
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.transcript = transcript
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def handle_turn(self, prompt: str, model: str | None = None) -> None:
        self.transcript.append("user", prompt)
        self.messages.append({"role": "user", "content": prompt})
        print(f"Nova: {prompt}\n", flush=True)
        for _ in range(self.settings.max_turns):
            payload = self.llm.complete(self.messages, self.tools.openai_tools(), model=model)
            message = _assistant_message(payload)
            content = str(message.get("content") or "").strip()
            tool_calls = message.get("tool_calls") or []
            if content:
                thought, reply = _split_thought(content)
                if thought:
                    self.transcript.append("thinking", thought)
                    print(f"Thought: {thought}\n", flush=True)
                if reply:
                    self.transcript.append("reply", reply)
                    print(reply + "\n", flush=True)
            self.messages.append(message)
            if not tool_calls:
                if not content:
                    self.transcript.append("reply", "Nova finished this turn without a text reply.")
                return
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "tool")
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                preview = json.dumps(args, default=str)[:800]
                self.transcript.append("tool", f"{name}\n{preview}", {"source_id": str(call.get("id") or name)})
                print(f"[tool] {name}\n", flush=True)
                result = self.tools.execute(name, args if isinstance(args, dict) else {})
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "content": result[:8000],
                })
        self.transcript.append("error", "Nova stopped after the maximum number of tool steps.")


def _assistant_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("AI Gateway returned no choices.")
    message = choices[0].get("message") or {}
    return {
        "role": "assistant",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls") or [],
    }


def _split_thought(content: str) -> tuple[str, str]:
    text = content.strip()
    if text.lower().startswith("thought:"):
        rest = text[8:].lstrip()
        parts = rest.split("\n\n", 1)
        return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    return "", text


