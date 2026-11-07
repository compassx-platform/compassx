"""Platform tools: HTTP to CompassX, never local DB or secrets."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from sandbox_nova.config import NovaSettings
from sandbox_nova.tools.base import NovaTool

PLATFORM_TOOL_SPECS = (
    ("sql_warehouse", "Run SQL against the CompassX SQL warehouse.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
            "sql": {"type": "string"},
        },
    }),
    ("catalog", "Discover and inspect CompassX catalog objects.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
        },
    }),
    ("search_assets", "Search CompassX assets.", {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }),
    ("catalog_editor", "Create or change catalog objects.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
        },
    }),
    ("notebook_manager", "Create, edit, and run CompassX notebooks.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
        },
    }),
    ("dashboard_manager", "Create and edit CompassX dashboards.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
        },
    }),
    ("mlflow", "Use MLflow on CompassX.", {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "payload": {"type": "object"},
        },
    }),
    ("rag_search", "Search attached documents and RAG indexes.", {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }),
    ("visualization", "Build a visualization from data.", {
        "type": "object",
        "properties": {
            "data": {"type": "object"},
            "chart_type": {"type": "string"},
        },
    }),
    ("invoke_agent", "Invoke another CompassX agent.", {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "prompt": {"type": "string"},
        },
    }),
    ("create_plan", "Create an execution plan checkpoint.", {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "steps": {"type": "array"},
        },
    }),
    ("get_plan", "Read the active plan.", {"type": "object", "properties": {"plan_id": {"type": "string"}}}),
    ("get_next_step", "Get the next pending plan step.", {"type": "object", "properties": {"plan_id": {"type": "string"}}}),
    ("mark_step", "Mark a plan step status.", {
        "type": "object",
        "properties": {
            "plan_id": {"type": "string"},
            "step_id": {"type": "string"},
            "status": {"type": "string"},
        },
    }),
    ("append_correction", "Record a correction on the plan.", {
        "type": "object",
        "properties": {
            "plan_id": {"type": "string"},
            "note": {"type": "string"},
        },
    }),
    ("escalate_to_plan", "Escalate the current turn into a plan.", {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
    }),
    ("list_available_skills", "List CompassX skills.", {"type": "object", "properties": {}}),
    ("read_skill", "Read a CompassX skill.", {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }),
)

PLATFORM_TOOL_NAMES = {spec[0] for spec in PLATFORM_TOOL_SPECS}


class PlatformTool(NovaTool):
    def __init__(self, name: str, description: str, parameters: dict[str, Any], settings: NovaSettings) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.settings = settings

    def execute(self, arguments: dict[str, Any]) -> str:
        if not self.settings.platform_url or not self.settings.gateway_key:
            return "Platform API is not configured in this sandbox."
        payload = json.dumps({
            "name": self.name,
            "arguments": arguments or {},
            "session_id": self.settings.session_id,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.platform_url}/agent-runtime/sandbox/tools",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.gateway_key}",
                "Content-Type": "application/json",
                "X-CompassX-Runtime-Session": self.settings.session_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read().decode("utf-8", errors="replace")[:8000]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            return f"Platform tool HTTP {exc.code}: {detail}"
