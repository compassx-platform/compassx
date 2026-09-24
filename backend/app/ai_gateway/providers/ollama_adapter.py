"""Ollama and generic OpenAI-compatible local model provider adapter."""

from __future__ import annotations

import logging
import httpx

from app.ai_gateway.providers.base import ProviderCredentials
from app.ai_gateway.providers.openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class OllamaAdapter(OpenAIAdapter):
    """Adapter for local Ollama instances (exposes OpenAI-compatible endpoints at /v1)."""

    def _get_base_url(self, creds: ProviderCredentials, is_azure: bool = False) -> str:
        return (creds.base_url or "http://localhost:11434/v1").rstrip("/")

    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        base_url = self._get_base_url(creds)
        timeout = httpx.Timeout(5.0, connect=3.0)

        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.get(f"{base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    model_ids = [m.get("id") for m in data.get("data", []) if "id" in m]
                    return True, "Successfully connected to Ollama instance", model_ids
                else:
                    return False, f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}", []
        except Exception as e:
            return False, f"Ollama connection failed: {str(e)}", []
