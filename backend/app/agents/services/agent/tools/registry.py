"""Tool registry - single source of truth for all available agent tools."""

from __future__ import annotations

from typing import Any

from app.agents.services.agent.tools.base_tool import BaseTool
from app.agents.services.agent.tools.sql_query_tool import SqlQueryTool
from app.agents.services.agent.tools.python_code_tool import PythonCodeTool
from app.agents.services.agent.tools.visualization_tool import VisualizationTool
from app.agents.services.agent.tools.rag_search_tool import RagSearchTool
from app.agents.services.agent.tools.claude_agent_tool import ClaudeAgentTool
from app.agents.services.agent.tools.git_workspace_tool import GitWorkspaceTool
from app.agents.services.agent.tools.invoke_agent_tool import InvokeAgentTool
from app.agents.services.agent.tools.fetch_memory_tool import FetchMemoryTool
from app.agents.services.agent.tools.research_memory_tool import FetchResearchMemoryTool, SaveResearchMemoryTool
from app.agents.services.agent.tools.research_engine_tools import (
    HarvestResearchMemoryTool,
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

def _get_default_tools() -> list[BaseTool]:
    tools: list[BaseTool] = []
    try:
        from app.nova.services.tools.fetch_attachment_tool import FetchAttachmentTool
        tools.append(FetchAttachmentTool())
    except ImportError:
        pass
    return tools

TOOL_REGISTRY: list[BaseTool] = _get_default_tools() + [
    SqlQueryTool(),
    PythonCodeTool(),
    VisualizationTool(),
    RagSearchTool(),
    GitWorkspaceTool(),
    ClaudeAgentTool(),
    AssetManagerTool(),
    NotebookManagerTool(),
    DashboardManagerTool(),
    InvokeAgentTool(),
    FetchMemoryTool(),
    FetchResearchMemoryTool(),
    SaveResearchMemoryTool(),
    HarvestResearchMemoryTool(),
    FetchLayer1ProfilesTool(),
    ScanPlatformMaturityTool(),
    FetchResearchProposalHistoryTool(),
    ListAvailableSkillsTool(),
    ReadSkillTool(),
    ListTablesTool(),
    GetTableSchemaTool(),
    GetColumnStatsTool(),
    CheckValueOverlapTool(),
    SearchWorkspaceTool(),
    GetDataProfileTool(),
    SaveDataProfileTool(),
    GetExistingProfileTool(),
    DatabaseExplorerTool(),
    SearchAssetsTool(),
    CreateNotebookTool(),
    SearchCatalogMetadataTool(),
    CatalogEditorTool(),
    CreatePlanTool(),
    GetPlanTool(),
    MarkStepTool(),
    AppendCorrectionTool(),
    GetNextStepTool(),
    EscalateToPlanTool(),
]

TOOL_MAP: dict[str, BaseTool] = {t.key: t for t in TOOL_REGISTRY}


def get_tool_definitions(
    tool_keys: list[str],
    allowed_tool_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return OpenAI-compatible tool definitions for the given keys."""
    definitions = []
    for key in tool_keys:
        tool = TOOL_MAP.get(key)
        if tool is None:
            continue
        if allowed_tool_names is not None and key not in allowed_tool_names:
            continue
        definitions.append(tool.to_openai_definition())
    return definitions
