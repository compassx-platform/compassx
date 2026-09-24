"""Unit tests for AI Gateway Provider Adapters."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.ai_gateway.models.provider import AIProviderType
from app.ai_gateway.providers.base import ProviderCredentials
from app.ai_gateway.providers.factory import get_provider_adapter
from app.ai_gateway.providers.openai_adapter import OpenAIAdapter
from app.ai_gateway.providers.anthropic_adapter import AnthropicAdapter
from app.ai_gateway.providers.gemini_adapter import GeminiAdapter
from app.ai_gateway.providers.ollama_adapter import OllamaAdapter
from app.ai_gateway.schemas.chat import (
    ChatMessage,
    ChatCompletionRequest,
    ToolDefinition,
    ToolDefinitionFunction,
)


@pytest.mark.asyncio
async def test_provider_factory():
    openai_adapter = get_provider_adapter(AIProviderType.openai)
    assert isinstance(openai_adapter, OpenAIAdapter)

    anthropic_adapter = get_provider_adapter(AIProviderType.anthropic)
    assert isinstance(anthropic_adapter, AnthropicAdapter)

    gemini_adapter = get_provider_adapter(AIProviderType.gemini)
    assert isinstance(gemini_adapter, GeminiAdapter)

    ollama_adapter = get_provider_adapter(AIProviderType.ollama)
    assert isinstance(ollama_adapter, OllamaAdapter)


@pytest.mark.asyncio
async def test_anthropic_message_conversion():
    adapter = AnthropicAdapter()
    req = ChatCompletionRequest(
        model="claude-3-5-sonnet",
        messages=[
            ChatMessage(role="system", content="You are a helpful data assistant."),
            ChatMessage(role="user", content="Hello Claude"),
        ],
        tools=[
            ToolDefinition(
                type="function",
                function=ToolDefinitionFunction(
                    name="query_db",
                    description="Run SQL query",
                    parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
                ),
            )
        ],
    )

    sys_prompt, messages = adapter._convert_messages_and_system(req)
    assert sys_prompt == "You are a helpful data assistant."
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello Claude"

    tools = adapter._convert_tools(req)
    assert tools is not None
    assert len(tools) == 1
    assert tools[0]["name"] == "query_db"
    assert "input_schema" in tools[0]


@pytest.mark.asyncio
async def test_gemini_message_conversion():
    adapter = GeminiAdapter()
    req = ChatCompletionRequest(
        model="gemini-2.5-flash",
        messages=[
            ChatMessage(role="system", content="System instruction"),
            ChatMessage(role="user", content="Hi Gemini"),
            ChatMessage(role="assistant", content="Hello! How can I help?"),
        ],
    )

    sys_inst, contents = adapter._convert_messages(req)
    assert sys_inst is not None
    assert sys_inst["parts"][0]["text"] == "System instruction"
    assert len(contents) == 2
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"


@pytest.mark.asyncio
async def test_openai_payload_preparation():
    adapter = OpenAIAdapter()
    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[
            ChatMessage(role="user", content="Test query"),
        ],
        temperature=0.5,
        max_tokens=1000,
    )

    payload = adapter._prepare_payload(req, "gpt-4o-2024-08-06")
    assert payload["model"] == "gpt-4o-2024-08-06"
    assert payload["temperature"] == 0.5
    assert payload["max_tokens"] == 1000
    assert len(payload["messages"]) == 1


@pytest.mark.asyncio
async def test_openai_discover_models_no_key():
    adapter = OpenAIAdapter()
    creds = ProviderCredentials(api_key=None, base_url="https://api.openai.com/v1")
    success, message, models = await adapter.ping(creds)
    assert success is False
    assert "API key" in message
    assert models == []


@pytest.mark.asyncio
async def test_anthropic_discover_models_no_key():
    adapter = AnthropicAdapter()
    creds = ProviderCredentials(api_key=None)
    success, message, models = await adapter.ping(creds)
    assert success is False
    assert "API key" in message
    assert models == []


@pytest.mark.asyncio
async def test_azure_discover_models_query_params():
    adapter = OpenAIAdapter()
    creds = ProviderCredentials(
        provider_type="azure",
        api_key="mock-key",
        base_url="https://mock-res.openai.azure.com/openai",
        config={"azure_resource_name": "mock-res", "api_version": "2024-02-01"},
    )
    assert adapter._is_azure(creds) is True
    assert adapter._get_api_version(creds) == "2024-02-01"
    assert adapter._get_base_url(creds, is_azure=True) == "https://mock-res.openai.azure.com/openai"
    headers = adapter._get_headers(creds, is_azure=True)
    assert headers.get("api-key") == "mock-key"


@pytest.mark.asyncio
async def test_azure_placeholder_url():
    adapter = OpenAIAdapter()
    creds = ProviderCredentials(
        provider_type="azure",
        api_key="mock-key",
        base_url="https://<your-resource>.openai.azure.com/openai",
        config={"azure_resource_name": "my-real-res"},
    )
    assert adapter._get_base_url(creds, is_azure=True) == "https://my-real-res.openai.azure.com/openai"


@pytest.mark.asyncio
async def test_azure_services_ai_foundry_url():
    adapter = OpenAIAdapter()
    creds = ProviderCredentials(
        provider_type="compatible",
        api_key="mock-key",
        base_url="https://test0002.services.ai.azure.com",
        config={"is_azure": False, "azure_resource_name": ""},
    )
    assert adapter._is_azure(creds) is True
    assert adapter._get_base_url(creds, is_azure=True) == "https://test0002.services.ai.azure.com/openai"
    headers = adapter._get_headers(creds, is_azure=True)
    assert headers.get("api-key") == "mock-key"
    assert headers.get("Authorization") == "Bearer mock-key"




