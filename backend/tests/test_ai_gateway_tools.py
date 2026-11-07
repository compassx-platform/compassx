"""Gateway tool parsing and Azure Foundry URL construction."""
import unittest

from app.ai_gateway.models.provider import AIProviderType
from app.ai_gateway.providers.anthropic_adapter import AnthropicAdapter
from app.ai_gateway.providers.base import ProviderCredentials
from app.ai_gateway.providers.factory import get_provider_adapter
from app.ai_gateway.providers.grok_adapter import GrokAdapter
from app.ai_gateway.providers.openai_adapter import OpenAIAdapter
from app.ai_gateway.schemas.chat import ChatCompletionRequest


class TestGatewayToolsAndFoundry(unittest.TestCase):
    def test_anthropic_tools_from_dicts(self):
        req = ChatCompletionRequest.model_validate({
            "model": "claude-haiku-5-5",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }],
        })
        tools = AnthropicAdapter()._convert_tools(req)
        self.assertEqual(tools[0]["name"], "list_files")
        self.assertEqual(tools[0]["input_schema"]["properties"]["path"]["type"], "string")

    def test_foundry_chat_url_uses_models_not_deployments(self):
        adapter = OpenAIAdapter()
        creds = ProviderCredentials(
            api_key="test-key",
            base_url="https://test0002.services.ai.azure.com",
            config={"api_version": "2024-05-01-preview"},
        )
        self.assertTrue(adapter._is_azure(creds))
        self.assertTrue(adapter._is_azure_foundry(creds))
        base = adapter._get_base_url(creds, True)
        url = adapter._azure_resource_url(creds, base, "gpt-5.4-mini", "chat")
        self.assertIn("/models/chat/completions", url)
        self.assertNotIn("/openai/deployments/", url)
        self.assertNotIn("/openai/", url)

    def test_grok_adapter_uses_xai_default_url(self):
        adapter = get_provider_adapter(AIProviderType.grok)
        self.assertIsInstance(adapter, GrokAdapter)
        creds = ProviderCredentials(api_key="xai-test", base_url=None)
        self.assertEqual(adapter._get_base_url(creds), "https://api.x.ai/v1")
        custom = ProviderCredentials(api_key="xai-test", base_url="https://api.x.ai/v1/")
        self.assertEqual(adapter._get_base_url(custom), "https://api.x.ai/v1")

    def test_grok_rejects_api_key_shaped_model_ids(self):
        from app.ai_gateway.providers.grok_adapter import is_grok_api_key_shaped

        self.assertTrue(is_grok_api_key_shaped("xai-abc"))
        self.assertTrue(is_grok_api_key_shaped("grok_" + "a" * 32 + "_" + "b" * 64))
        self.assertFalse(is_grok_api_key_shaped("grok-4"))
        self.assertFalse(is_grok_api_key_shaped("grok-3-mini"))

    def test_grok_extracts_language_model_ids(self):
        adapter = GrokAdapter()
        ids = adapter._model_ids_from_payload({
            "models": [
                {"id": "grok-4.7", "aliases": ["grok-4.7-latest"], "output_modalities": ["text"]},
                {"id": "grok-4.6", "output_modalities": ["text"]},
                {"id": "grok-imagine-image", "output_modalities": ["image"]},
                {"id": "grok_" + "a" * 32 + "_" + "b" * 64, "output_modalities": ["text"]},
            ]
        })
        self.assertEqual(ids, ["grok-4.7", "grok-4.7-latest", "grok-4.6"])
