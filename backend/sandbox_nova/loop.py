"""Nova agent loop: LLM + tools + transcript. Independent of CompassX host process."""

from __future__ import annotations

import json
import os
from typing import Any

from sandbox_nova.config import NovaSettings
from sandbox_nova.llm import GatewayLLM
from sandbox_nova.modes import mode_prompt, normalize_mode, reply_kind, tool_definitions
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

    def handle_turn(self, prompt: str, model: str | None = None, mode: str | None = None) -> None:
        selected = normalize_mode(mode)
        self.transcript.append("user", prompt)
        addendum = mode_prompt(selected)
        self.messages.append({"role": "user", "content": f"{addendum}\n\n{prompt}" if addendum else prompt})
        print(f"Nova: {prompt}\n", flush=True)
        visible_tools = tool_definitions(self.tools.openai_tools(), selected)
        allowed = {((item.get("function") or {}).get("name")) for item in visible_tools}
        for _ in range(self.settings.max_turns):
            if self._stopped():
                return
            payload = self.llm.complete(self.messages, visible_tools, model=model)
            message = _assistant_message(payload)
            content = str(message.get("content") or "").strip()
            tool_calls = message.get("tool_calls") or []
            thought, reply = "", ""
            if content:
                thought, reply = _split_thought(content)
                if thought:
                    self.transcript.append("thinking", thought)
                    print(f"Thought: {thought}\n", flush=True)
                if reply:
                    self.transcript.append(reply_kind(selected), reply)
                    print(reply + "\n", flush=True)
            self.messages.append(message)
            if not tool_calls:
                if not reply:
                    self.transcript.append(reply_kind(selected), thought or "Nova finished this turn without a text reply.")
                return
            if self._stopped():
                return
            for call in tool_calls:
                if self._stopped():
                    return
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
                if name not in allowed:
                    result = f"{name} is not available in {selected} mode."
                else:
                    result = self.tools.execute(name, args if isinstance(args, dict) else {})
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "content": result[:8000],
                })
        self.transcript.append("error", "Nova stopped after the maximum number of tool steps.")

    def _stopped(self) -> bool:
        path = os.path.join(self.settings.state_dir, "stop")
        if not os.path.isfile(path):
            return False
        try:
            os.remove(path)
        except OSError:
            pass
        self.transcript.append("error", "Stopped.")
        print("Stopped.\n", flush=True)
        return True


def _assistant_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("AI Gateway returned no choices.")
    message = choices[0].get("message") or {}
    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def _split_thought(content: str) -> tuple[str, str]:
    text = content.strip()
    if not text.lower().startswith("thought:"):
        return "", text
    rest = text[8:].lstrip()
    if not rest:
        return "", ""
    if "\n\n" in rest:
        thought, reply = rest.split("\n\n", 1)
        return thought.strip(), reply.strip()
    head, _, tail = rest.partition("\n")
    if tail.strip():
        return head.strip(), tail.strip()
    return rest.strip(), ""


