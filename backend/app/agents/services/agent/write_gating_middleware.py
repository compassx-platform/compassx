"""Write-Gating Middleware enforcing Part A rules (D1, D2, D3, D4, D10, D11)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.agents.schemas.agent_manifest import AgentManifest


class WriteGatingViolation(Exception):
    def __init__(self, message: str, category: str, checkpoint_type: str):
        super().__init__(message)
        self.category = category
        self.checkpoint_type = checkpoint_type


class WriteGatingMiddleware:
    """Enforces write-gating and checkpoint rules centrally across tool execution."""

    CATEGORY_MAP = {
        "catalog": ["create_table", "register_table", "alter_table", "drop_table", "create_schema"],
        "storage": ["write_volume_file", "put_object", "delete_object"],
        "scheduler": ["create_job", "update_job", "schedule_job"],
        "dashboard": ["create_dashboard", "update_dashboard"],
        "app": ["create_app", "deploy_app", "update_app"],
    }

    UN_GATED_TOOL_PREFIXES = [
        "read_", "get_", "list_", "describe_", "sample_", "inspect_", "search_",
        "execute_sql", "run_sql", "query_sql", "sql_query", "db_introspect",
    ]

    def __init__(self, manifest: Optional[AgentManifest] = None):
        self.manifest = manifest or AgentManifest()

    def get_tool_category(self, tool_name: str) -> Optional[str]:
        for category, tools in self.CATEGORY_MAP.items():
            if tool_name in tools or any(tool_name.startswith(f"{cat}_") for cat in [category]):
                return category
        return None

    def is_gated_write_tool(self, tool_name: str) -> bool:
        if not self.manifest.capabilities.checkpoints.enabled:
            return False

        # Rule A2 & D2: Inspection actions never require a checkpoint
        if any(tool_name.startswith(prefix) for prefix in self.UN_GATED_TOOL_PREFIXES):
            return False

        category = self.get_tool_category(tool_name)
        if category and category in self.manifest.capabilities.checkpoints.gated_write_categories:
            return True
        return False

    def validate_tool_execution(
        self,
        tool_name: str,
        plan_approved: bool,
        execution_approved: bool,
        is_first_real_run: bool = False,
    ) -> None:
        """Validates tool call against 2-gate checkpoint rules."""
        if not self.is_gated_write_tool(tool_name):
            return

        category = self.get_tool_category(tool_name) or "write"

        # Gate 1: Plan approval check
        if not plan_approved:
            raise WriteGatingViolation(
                message=f"Tool '{tool_name}' (category: {category}) requires prior Plan Checkpoint approval.",
                category=category,
                checkpoint_type="plan_checkpoint",
            )

        # Gate 2: Execution approval check before first run against real data
        if is_first_real_run and not execution_approved:
            raise WriteGatingViolation(
                message=f"Tool '{tool_name}' executing first real run requires Execution Checkpoint approval.",
                category=category,
                checkpoint_type="execution_checkpoint",
            )
