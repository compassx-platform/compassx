"""OpenAI and Azure OpenAI Provider Adapter."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

import httpx

from app.ai_gateway.providers.base import BaseProviderAdapter, ProviderCredentials
from app.ai_gateway.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionDelta,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    FunctionCall,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for OpenAI, Azure OpenAI, Azure AI Foundry, and generic OpenAI-compatible APIs."""

    def _is_azure(self, creds: ProviderCredentials) -> bool:
        config = creds.config or {}
        if config.get("is_azure"):
            return True
        p_type = getattr(creds, "provider_type", None)
        if p_type:
            val = p_type.value if hasattr(p_type, "value") else str(p_type)
            if "azure" in val.lower():
                return True
        base_url = (creds.base_url or "").lower()
        if "azure" in base_url:
            return True
        if config.get("azure_resource_name"):
            return True
        return False

    def _get_api_version(self, creds: ProviderCredentials) -> str:
        config = creds.config or {}
        return (
            config.get("api_version")
            or config.get("azure_api_version")
            or "2024-06-01"
        )

    def _get_base_url(self, creds: ProviderCredentials, is_azure: bool = False) -> str:
        config = creds.config or {}
        raw_url = (creds.base_url or "").strip()

        # If Azure and URL is placeholder with <...>, construct from resource name
        if is_azure and ("<" in raw_url or not raw_url):
            resource = (config.get("azure_resource_name") or "").strip()
            if resource:
                return f"https://{resource}.openai.azure.com/openai"
            return "https://compassx.openai.azure.com/openai"

        if raw_url:
            url = raw_url.rstrip("/")
            if is_azure:
                url_lower = url.lower()
                # If it's an Azure domain and doesn't have /openai or /models or /v1, append /openai
                if any(domain in url_lower for domain in ["openai.azure.com", "services.ai.azure.com", "cognitiveservices.azure.com", "azure.com"]):
                    if not url_lower.endswith("/openai") and not url_lower.endswith("/models") and not url_lower.endswith("/v1"):
                        url = f"{url}/openai"
            return url

        if is_azure:
            resource = (config.get("azure_resource_name") or "").strip()
            if resource:
                return f"https://{resource}.openai.azure.com/openai"
        return "https://api.openai.com/v1"

    def _get_headers(self, creds: ProviderCredentials, is_azure: bool = False) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        config = creds.config or {}
        if creds.api_key:
            if is_azure:
                headers["api-key"] = creds.api_key
                headers["Authorization"] = f"Bearer {creds.api_key}"
            else:
                headers["Authorization"] = f"Bearer {creds.api_key}"
                base_url = (creds.base_url or "").lower()
                if "azure" in base_url:
                    headers["api-key"] = creds.api_key
        if config.get("organization_id"):
            headers["OpenAI-Organization"] = config["organization_id"]
        return headers

    def _prepare_payload(self, request: ChatCompletionRequest, upstream_model: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": upstream_model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.presence_penalty is not None:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.tools:
            payload["tools"] = [tool.model_dump(exclude_none=True) for tool in request.tools]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        return payload

    async def chat_stream(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> AsyncIterator[ChatCompletionChunk]:
        is_azure = self._is_azure(creds)
        base_url = self._get_base_url(creds, is_azure)
        headers = self._get_headers(creds, is_azure)

        if is_azure:
            api_version = self._get_api_version(creds)
            if base_url.endswith("/models"):
                url = f"{base_url}/chat/completions?api-version={api_version}"
            else:
                url = f"{base_url}/deployments/{upstream_model}/chat/completions?api-version={api_version}"
        else:
            url = f"{base_url}/chat/completions"

        payload = self._prepare_payload(request, upstream_model)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    error_text = error_body.decode(errors="replace")
                    raise RuntimeError(f"OpenAI API error ({response.status_code}): {error_text}")

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break

                    try:
                        chunk_dict = json.loads(line)
                        yield ChatCompletionChunk.model_validate(chunk_dict)
                    except Exception:
                        continue

    async def chat_complete(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> ChatCompletionResponse:
        is_azure = self._is_azure(creds)
        base_url = self._get_base_url(creds, is_azure)
        headers = self._get_headers(creds, is_azure)

        if is_azure:
            api_version = self._get_api_version(creds)
            if base_url.endswith("/models"):
                url = f"{base_url}/chat/completions?api-version={api_version}"
            else:
                url = f"{base_url}/deployments/{upstream_model}/chat/completions?api-version={api_version}"
        else:
            url = f"{base_url}/chat/completions"

        payload = self._prepare_payload(request, upstream_model)
        payload["stream"] = False

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            return ChatCompletionResponse.model_validate(data)

    async def embed(
        self,
        texts: list[str],
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> list[list[float]]:
        is_azure = self._is_azure(creds)
        base_url = self._get_base_url(creds, is_azure)
        headers = self._get_headers(creds, is_azure)

        if is_azure:
            api_version = self._get_api_version(creds)
            if base_url.endswith("/models"):
                url = f"{base_url}/embeddings?api-version={api_version}"
            else:
                url = f"{base_url}/deployments/{upstream_model}/embeddings?api-version={api_version}"
        else:
            url = f"{base_url}/embeddings"

        payload = {"model": upstream_model, "input": texts}
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"OpenAI embedding error ({resp.status_code}): {resp.text}")
            data = resp.json()
            return [item["embedding"] for item in data.get("data", [])]

    def _extract_model_ids(self, data: Any) -> list[str]:
        raw_items = []
        if isinstance(data, dict):
            raw_items = data.get("data", []) or data.get("value", []) or data.get("models", [])
            if not raw_items and ("id" in data or "name" in data or "model" in data):
                raw_items = [data]
        elif isinstance(data, list):
            raw_items = data

        results = []
        for item in raw_items:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name") or item.get("model")
                if mid and isinstance(mid, str) and mid not in results:
                    results.append(mid)
            elif isinstance(item, str) and item not in results:
                results.append(item)
        return results

    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        is_azure = self._is_azure(creds)
        base_url = self._get_base_url(creds, is_azure)
        headers = self._get_headers(creds, is_azure)
        timeout = httpx.Timeout(12.0, connect=5.0)

        # Validation for Azure credentials
        if is_azure:
            if not creds.api_key:
                return False, "Please enter an Azure API Key to discover live models.", []
            config = creds.config or {}
            resource_name = (config.get("azure_resource_name") or "").strip()
            if "<your-resource>" in base_url or (not creds.base_url and not resource_name):
                return False, "Please enter a valid Azure Resource Name or Base URL to discover live models.", []
        else:
            if not creds.api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
                return False, "Please enter an API key to discover live models from OpenAI.", []

        # Standard OpenAI / OpenAI-compatible Ping
        if not is_azure:
            try:
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    models_url = f"{base_url}/models"
                    resp = await client.get(models_url, headers=headers)
                    if resp.status_code == 200:
                        model_ids = self._extract_model_ids(resp.json())
                        return True, "Successfully connected to OpenAI", model_ids
                    elif resp.status_code in (401, 403):
                        return False, "Invalid API key or unauthorized (HTTP 401/403)", []
                    else:
                        return False, f"Provider returned HTTP {resp.status_code}: {resp.text[:200]}", []
            except Exception as e:
                return False, f"Connection failed: {str(e)}", []

        # Azure OpenAI / Azure AI Services Discovery
        configured_ver = (creds.config or {}).get("azure_api_version") or (creds.config or {}).get("api_version")
        candidate_versions = []
        if configured_ver and configured_ver.strip():
            candidate_versions.append(configured_ver.strip())

        standard_azure_versions = [
            "2024-06-01",
            "2024-10-21",
            "2024-02-01",
            "2023-05-15",
            "2024-08-01-preview",
            "2024-05-01-preview",
            "2024-02-15-preview",
            "2023-12-01-preview",
            "2023-03-15-preview",
            "2022-12-01",
        ]
        for v in standard_azure_versions:
            if v not in candidate_versions:
                candidate_versions.append(v)

        # Base URLs to test (with and without /openai)
        if base_url.endswith("/openai"):
            url_with_openai = base_url
            url_without_openai = base_url[:-7]
        else:
            url_with_openai = f"{base_url}/openai"
            url_without_openai = base_url

        last_error = ""
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                # 1. Primary check: Query /deployments endpoint (discovering real, active Azure deployments)
                for ver in candidate_versions:
                    deployments_urls = [
                        f"{url_with_openai}/deployments?api-version={ver}",
                        f"{url_without_openai}/deployments?api-version={ver}",
                    ]

                    for dep_url in deployments_urls:
                        try:
                            resp = await client.get(dep_url, headers=headers)
                        except Exception as req_err:
                            last_error = str(req_err)
                            continue

                        if resp.status_code == 200:
                            dep_ids = self._extract_model_ids(resp.json())
                            if dep_ids:
                                return True, f"Successfully discovered {len(dep_ids)} active deployments from Azure AI ({ver})", dep_ids
                            else:
                                return True, f"Connected to Azure OpenAI ({ver}), but no active deployments were found. You can add your deployment name manually.", []

                        if resp.status_code in (401, 403):
                            return False, "Invalid Azure API key or unauthorized access to resource (HTTP 401/403)", []

                        last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"

                # 2. Secondary check for Serverless / Model-as-a-Service on Azure AI Foundry (/models)
                for ver in candidate_versions:
                    models_urls = [
                        f"{url_without_openai}/models",
                        f"{url_without_openai}/models?api-version={ver}",
                        f"{url_with_openai}/models?api-version={ver}",
                    ]

                    for m_url in models_urls:
                        try:
                            resp = await client.get(m_url, headers=headers)
                        except Exception as req_err:
                            last_error = str(req_err)
                            continue

                        if resp.status_code == 200:
                            model_ids = self._extract_model_ids(resp.json())
                            if model_ids:
                                return True, f"Successfully discovered {len(model_ids)} models from Azure AI ({ver})", model_ids

                        if resp.status_code in (401, 403):
                            return False, "Invalid Azure API key or unauthorized access to resource (HTTP 401/403)", []

                        last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"

                return False, f"Could not list Azure OpenAI deployments ({last_error}). You can add your deployment name manually using the quick input above.", []
        except Exception as e:
            return False, f"Azure connection failed: {str(e)}. You can add your deployment name manually using the quick input above.", []
