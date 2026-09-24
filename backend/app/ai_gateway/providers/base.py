"""Base Provider Adapter Interface and Data Classes for AI Gateway."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.ai_gateway.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)


@dataclass
class ProviderCredentials:
    provider_type: Any | None = None
    api_key: str | None = None
    base_url: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


class BaseProviderAdapter(ABC):
    """Abstract base class for all external AI model provider adapters."""

    @abstractmethod
    async def chat_stream(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream chat completions chunk by chunk in OpenAI format."""
        pass

    @abstractmethod
    async def chat_complete(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> ChatCompletionResponse:
        """Return non-streaming chat completion in OpenAI format."""
        pass

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> list[list[float]]:
        """Generate vector embeddings for input texts."""
        pass

    @abstractmethod
    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        """Test provider connectivity and return (success, message, available_models)."""
        pass
