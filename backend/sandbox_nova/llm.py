"""OpenAI-compatible chat completions client (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from sandbox_nova.config import NovaSettings


class GatewayLLM:
    def __init__(self, settings: NovaSettings) -> None:
        self.settings = settings

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str | None = None) -> dict[str, Any]:
        if not self.settings.gateway_url or not self.settings.gateway_key:
            raise RuntimeError("AI Gateway is not configured in this sandbox.")
        payload: dict[str, Any] = {
            "model": (model or self.settings.model).strip() or self.settings.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.settings.chat_completions_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.gateway_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"AI Gateway HTTP {exc.code}: {detail}") from exc
