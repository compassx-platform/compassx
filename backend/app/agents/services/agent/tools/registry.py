"""Tool registry - single source of truth for all available agent tools."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.agents.services.agent.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Thread-safe registry for agent tools adhering to Open-Closed and Dependency Inversion principles."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tools: dict[str, BaseTool] = {}
        self._initialized = False

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        with self._lock:
            self._tools[tool.key] = tool

    def unregister(self, tool_key: str) -> None:
        """Unregister a tool by key."""
        with self._lock:
            self._tools.pop(tool_key, None)

    def get(self, tool_key: str) -> BaseTool | None:
        """Retrieve a registered tool by key."""
        self._ensure_initialized()
        with self._lock:
            return self._tools.get(tool_key)

    def list_tools(self) -> list[BaseTool]:
        """Return a list of all registered tools."""
        self._ensure_initialized()
        with self._lock:
            return list(self._tools.values())

    def get_definitions(
        self,
        tool_keys: list[str],
        allowed_tool_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions for the given keys."""
        self._ensure_initialized()
        definitions = []
        with self._lock:
            for key in tool_keys:
                tool = self._tools.get(key)
                if tool is None:
                    continue
                if allowed_tool_names is not None and key not in allowed_tool_names:
                    continue
                definitions.append(tool.to_openai_definition())
        return definitions

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._load_core_tools()
            self._initialized = True

    def _load_core_tools(self) -> None:
        # Load optional Nova tools
        try:
            from app.nova.services.tools.fetch_attachment_tool import FetchAttachmentTool
            self.register(FetchAttachmentTool())
        except ImportError:
            pass

        # Load core agent tools
        from app.agents.services.agent.tools.sql_query_tool import SqlQueryTool
        from app.agents.services.agent.tools.python_code_tool import PythonCodeTool
        from app.agents.services.agent.tools.visualization_tool import VisualizationTool
        from app.agents.services.agent.tools.rag_search_tool import RagSearchTool
        from app.agents.services.agent.tools.claude_agent_tool import ClaudeAgentTool
        from app.agents.services.agent.tools.git_workspace_tool import GitWorkspaceTool
        from app.agents.services.agent.tools.invoke_agent_tool import InvokeAgentTool
        from app.agents.services.agent.tools.research_engine_tools import (
            FetchLayer1ProfilesTool,
            ScanPlatformMaturityTool,
            FetchResearchProposalHistoryTool,
        )
        from app.agents.services.agent.tools.platform.asset_manager import AssetManagerTool
        from app.agents.services.agent.tools.platform.notebooks import NotebookManagerTool
        from app.agents.services.agent.tools.platform.dashboards import DashboardManagerTool
        from app.agents.services.agent.tools.list_available_skills_tool import ListAvailableSkillsTool
        from app.agents.services.agent.tools.read_skill_tool import ReadSkillTool
        from app.agents.services.agent.tools.profiling_tools import (
            ListTablesTool,
            GetTableSchemaTool,
            GetColumnStatsTool,
            CheckValueOverlapTool,
            SearchWorkspaceTool,
            SaveDataProfileTool,
            GetExistingProfileTool,
            GetDataProfileTool,
        )
        from app.agents.services.agent.tools.db_explorer_tool import DatabaseExplorerTool
        from app.agents.services.agent.tools.search_assets_tool import SearchAssetsTool
        from app.agents.services.agent.tools.create_notebook_tool import CreateNotebookTool
        from app.agents.services.agent.tools.search_catalog_metadata_tool import SearchCatalogMetadataTool
        from app.agents.services.agent.tools.catalog_editor_tool import CatalogEditorTool
        from app.agents.services.agent.tools.plan_tools import (
            CreatePlanTool,
            GetPlanTool,
            MarkStepTool,
            AppendCorrectionTool,
            GetNextStepTool,
        )
        from app.agents.services.agent.tools.escalate_plan_tool import EscalateToPlanTool

        core_tool_classes = [
            SqlQueryTool,
            PythonCodeTool,
            VisualizationTool,
            RagSearchTool,
            GitWorkspaceTool,
            ClaudeAgentTool,
            AssetManagerTool,
            NotebookManagerTool,
            DashboardManagerTool,
            InvokeAgentTool,
            FetchLayer1ProfilesTool,
            ScanPlatformMaturityTool,
            FetchResearchProposalHistoryTool,
            ListAvailableSkillsTool,
            ReadSkillTool,
            ListTablesTool,
            GetTableSchemaTool,
            GetColumnStatsTool,
            CheckValueOverlapTool,
            SearchWorkspaceTool,
            GetDataProfileTool,
            SaveDataProfileTool,
            GetExistingProfileTool,
            DatabaseExplorerTool,
            SearchAssetsTool,
            CreateNotebookTool,
            SearchCatalogMetadataTool,
            CatalogEditorTool,
            CreatePlanTool,
            GetPlanTool,
            MarkStepTool,
            AppendCorrectionTool,
            GetNextStepTool,
            EscalateToPlanTool,
        ]
        for cls in core_tool_classes:
            try:
                self.register(cls())
            except Exception as e:
                logger.warning("Failed to instantiate tool %s: %s", cls, e)


# Global singleton instance
tool_registry = ToolRegistry()


class _ToolMapProxy(dict):
    """Proxy dict for backward compatibility with TOOL_MAP."""

    def __getitem__(self, key: str) -> BaseTool:
        tool = tool_registry.get(key)
        if tool is None:
            raise KeyError(key)
        return tool

    def get(self, key: str, default: Any = None) -> Any:
        tool = tool_registry.get(key)
        return tool if tool is not None else default

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return tool_registry.get(key) is not None

    def values(self):
        return tool_registry.list_tools()

    def items(self):
        return [(t.key, t) for t in tool_registry.list_tools()]

    def keys(self):
        return [t.key for t in tool_registry.list_tools()]


class _ToolListProxy(list):
    """Proxy list for backward compatibility with TOOL_REGISTRY."""

    def __iter__(self):
        return iter(tool_registry.list_tools())

    def __len__(self):
        return len(tool_registry.list_tools())

    def __getitem__(self, index):
        return tool_registry.list_tools()[index]

    def append(self, tool: BaseTool) -> None:
        tool_registry.register(tool)


TOOL_MAP: dict[str, BaseTool] = _ToolMapProxy()
TOOL_REGISTRY: list[BaseTool] = _ToolListProxy()


def get_tool_definitions(
    tool_keys: list[str],
    allowed_tool_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    return tool_registry.get_definitions(tool_keys, allowed_tool_names)
