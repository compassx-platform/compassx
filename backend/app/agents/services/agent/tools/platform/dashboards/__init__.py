"""Dashboard platform tool package for agents."""

from app.agents.services.agent.tools.platform.dashboards.dashboard_manager_tool import DashboardManagerTool
from app.agents.services.agent.tools.platform.dashboards.operations import execute_dashboard_manager_operation

__all__ = ["DashboardManagerTool", "execute_dashboard_manager_operation"]
