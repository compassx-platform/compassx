from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

from app.models.agents import LLMProvider
from app.services.encryption import encrypt_field
from app.services.llm_client import chat_stream


class FakeFunctionCall:
    def __init__(self, name: str, args: dict, id: str | None = None, thought_signature: str | None = None):
        self.name = name
        self.args = args
        self.id = id
        self.thought_signature = thought_signature


class FakeFunctionResponse:
    def __init__(self, name: str, response: dict):
        self.name = name
        self.response = response


class FakePart:
    def __init__(
        self,
        text: str | None = None,
        function_call: FakeFunctionCall | None = None,
        function_response: FakeFunctionResponse | None = None,
        thought_signature: str | None = None,
        thoughtSignature: str | None = None,
        functionCall: FakeFunctionCall | None = None,
    ):
        self.text = text
        self.function_call = function_call or functionCall
        self.function_response = function_response
        self.thought_signature = thought_signature or thoughtSignature

    @classmethod
    def from_text(cls, text: str):
        return cls(text=text)

    @classmethod
    def from_function_response(cls, name: str, response: dict):
        return cls(function_response=FakeFunctionResponse(name=name, response=response))


class FakeContent:
    def __init__(self, role: str, parts: list[FakePart]):
        self.role = role
        self.parts = parts


class FakeFunctionDeclaration:
    def __init__(self, name: str, description: str, parameters: dict):
        self.name = name
        self.description = description
        self.parameters = parameters


class FakeTool:
    def __init__(self, function_declarations: list[FakeFunctionDeclaration]):
        self.function_declarations = function_declarations


class FakeGenerateContentConfig:
    def __init__(self, system_instruction=None, max_output_tokens=None, tools=None):
        self.system_instruction = system_instruction
        self.max_output_tokens = max_output_tokens
        self.tools = tools


class FakeUsageMetadata:
    prompt_token_count = 12
    response_token_count = 5
    total_token_count = 17


class FakeResponse:
    def __init__(self):
        self.candidates = [
            SimpleNamespace(
                content=FakeContent(
                    role="model",
                    parts=[
                        FakePart(text="Gemini says hello."),
                        FakePart(
                            function_call=FakeFunctionCall(
                                name="lookup_asset",
                                args={"asset_id": 42},
                                id="gemini_call_1",
                                thought_signature="sig-123",
                            ),
                            thought_signature="sig-123",
                        ),
                    ],
                )
            )
        ]
        self.usage_metadata = FakeUsageMetadata()


class FakeModelsAPI:
    def __init__(self):
        self.last_call = None

    async def generate_content(self, *, model, contents, config):
        self.last_call = {"model": model, "contents": contents, "config": config}
        return FakeResponse()


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.aio = SimpleNamespace(models=FakeModelsAPI())
        type(self).instances.append(self)


import pytest


@pytest.fixture()
def fake_google_genai(monkeypatch):
    FakeClient.instances.clear()

    fake_types = SimpleNamespace(
        Content=FakeContent,
        FunctionCall=FakeFunctionCall,
        FunctionDeclaration=FakeFunctionDeclaration,
        GenerateContentConfig=FakeGenerateContentConfig,
        Part=FakePart,
        Tool=FakeTool,
    )

    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    genai_module.Client = FakeClient
    genai_module.types = fake_types
    google_module.genai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)

    return FakeClient


def test_gemini_chat_stream_translates_history_and_tools(fake_google_genai):
    conn = SimpleNamespace(
        provider=LLMProvider.gemini,
        api_key_enc=encrypt_field("gemini-secret"),
        model_name="gemini-2.5-flash",
        max_tokens=1024,
        timeout_s=30,
        base_url=None,
        config={},
    )

    messages = [
        {"role": "user", "content": "Check the asset status."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "lookup_asset", "arguments": '{"asset_id": 42}'},
                    "thought_signature": "sig-previous",
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"status": "online"}'},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_asset",
                "description": "Look up an asset by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "integer"},
                        "payload": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["asset_id"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    async def collect_events():
        return [event async for event in chat_stream(conn, messages, tools, "You are a helpful assistant.")]

    events = asyncio.run(collect_events())
    declaration = fake_google_genai.instances[-1].aio.models.last_call["config"].tools[0].function_declarations[0]

    assert "additionalProperties" not in declaration.parameters
    assert "additionalProperties" not in declaration.parameters["properties"]["payload"]

    assert events == [
        {"type": "text", "delta": "Gemini says hello."},
        {
            "type": "tool_use",
            "tool_calls": [
                {
                    "id": "gemini_call_1",
                    "name": "lookup_asset",
                    "arguments": {"asset_id": 42},
                    "thought_signature": "sig-123",
                }
            ],
        },
        {"type": "done", "usage": {"input_tokens": 12, "output_tokens": 5}},
    ]

    client = fake_google_genai.instances[0]
    last_call = client.aio.models.last_call

    assert client.api_key == "gemini-secret"
    assert last_call["model"] == "gemini-2.5-flash"
    assert last_call["config"].system_instruction == "You are a helpful assistant."
    assert last_call["config"].max_output_tokens == 1024
    assert last_call["config"].tools[0].function_declarations[0].name == "lookup_asset"

    translated_contents = last_call["contents"]
    assert [content.role for content in translated_contents] == ["user", "model", "tool"]
    assert translated_contents[1].parts[0].function_call.name == "lookup_asset"
    assert translated_contents[1].parts[0].function_call.args == {"asset_id": 42}
    assert translated_contents[1].parts[0].thought_signature == "sig-previous"
    assert translated_contents[2].parts[0].function_response.name == "lookup_asset"
    assert translated_contents[2].parts[0].function_response.response == {"status": "online"}
