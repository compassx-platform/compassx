"""Provider Adapter Factory and Registry."""

from __future__ import annotations

from app.ai_gateway.models.provider import AIProviderType
from app.ai_gateway.providers.base import BaseProviderAdapter
from app.ai_gateway.providers.openai_adapter import OpenAIAdapter
from app.ai_gateway.providers.anthropic_adapter import AnthropicAdapter
from app.ai_gateway.providers.gemini_adapter import GeminiAdapter
from app.ai_gateway.providers.ollama_adapter import OllamaAdapter

_ADAPTER_REGISTRY: dict[AIProviderType, BaseProviderAdapter] = {
    AIProviderType.openai: OpenAIAdapter(),
    AIProviderType.azure: OpenAIAdapter(),
    AIProviderType.anthropic: AnthropicAdapter(),
    AIProviderType.gemini: GeminiAdapter(),
    AIProviderType.ollama: OllamaAdapter(),
    AIProviderType.compatible: OpenAIAdapter(),
}


def get_provider_adapter(provider_type: AIProviderType | str) -> BaseProviderAdapter:
    """Resolve the adapter instance for a given provider type."""
    if isinstance(provider_type, str):
        try:
            provider_type = AIProviderType(provider_type)
        except ValueError:
            provider_type = AIProviderType.compatible

    adapter = _ADAPTER_REGISTRY.get(provider_type)
    if not adapter:
        # Fallback to OpenAI-compatible adapter
        return _ADAPTER_REGISTRY[AIProviderType.compatible]
    return adapter
