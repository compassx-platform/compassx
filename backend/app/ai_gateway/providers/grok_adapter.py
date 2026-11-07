"""xAI Grok provider. OpenAI-compatible chat at api.x.ai."""

from __future__ import annotations

import logging
import re

import httpx

from app.ai_gateway.providers.base import ProviderCredentials
from app.ai_gateway.providers.http_client import gateway_http_client
from app.ai_gateway.providers.openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

_API_KEY_SHAPED = re.compile(
    r"^(xai-|grok_[0-9a-f]{16,}_)",
    re.IGNORECASE,
)


def is_grok_api_key_shaped(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if _API_KEY_SHAPED.match(text):
        return True
    return text.startswith("grok_") and len(text) > 40


class GrokAdapter(OpenAIAdapter):
    """Grok via the xAI OpenAI-compatible API. Model ids come from xAI list endpoints."""

    DEFAULT_BASE_URL = "https://api.x.ai/v1"

    def _get_base_url(self, creds: ProviderCredentials, is_azure: bool = False) -> str:
        raw = (creds.base_url or "").strip().rstrip("/")
        return raw or self.DEFAULT_BASE_URL

    def _auth_headers(self, creds: ProviderCredentials) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if creds.api_key:
            headers["Authorization"] = f"Bearer {creds.api_key.strip()}"
        return headers

    def _model_ids_from_payload(self, payload: object) -> list[str]:
        raw_items: list[object] = []
        if isinstance(payload, dict):
            raw_items = payload.get("data") or payload.get("models") or payload.get("value") or []
            if not raw_items and ("id" in payload or "name" in payload):
                raw_items = [payload]
        elif isinstance(payload, list):
            raw_items = payload

        results: list[str] = []
        for item in raw_items:
            if isinstance(item, str):
                mid = item.strip()
                if mid and not is_grok_api_key_shaped(mid) and mid not in results:
                    results.append(mid)
                continue
            if not isinstance(item, dict):
                continue
            outputs = item.get("output_modalities") or item.get("output_modality") or []
            if isinstance(outputs, str):
                outputs = [outputs]
            if outputs and "text" not in [str(m).lower() for m in outputs]:
                continue
            names = [item.get("id"), item.get("name"), item.get("model")]
            aliases = item.get("aliases") or []
            if isinstance(aliases, list):
                names.extend(aliases)
            for raw in names:
                if not isinstance(raw, str):
                    continue
                mid = raw.strip()
                if not mid or is_grok_api_key_shaped(mid) or mid in results:
                    continue
                results.append(mid)
        return results

    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        if not (creds.api_key or "").strip():
            return False, "Enter an xAI API key from console.x.ai.", []

        base_url = self._get_base_url(creds)
        headers = self._auth_headers(creds)
        timeout = httpx.Timeout(12.0, connect=5.0)
        last_error = ""

        try:
            async with gateway_http_client(timeout) as client:
                for path in ("/language-models", "/models"):
                    resp = await client.get(f"{base_url}{path}", headers=headers)
                    if resp.status_code == 200:
                        models = self._model_ids_from_payload(resp.json())
                        if models:
                            return True, "Successfully connected to xAI", models
                        last_error = f"{path} returned no models"
                        continue
                    if resp.status_code in (401, 403):
                        return False, "Invalid xAI API key (HTTP 401/403).", []
                    last_error = f"{path} HTTP {resp.status_code}: {(resp.text or '')[:200]}"
        except Exception as exc:
            return False, f"Connection failed: {exc}", []

        return False, f"xAI did not list models ({last_error or 'unknown error'}).", []
