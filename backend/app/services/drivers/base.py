"""Abstract base driver interfaces for App Deployments and Dev Sandboxes (SOLID / LSP / ISP)."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseAppDriver(ABC):
    """Abstract interface for deploying and managing production applications."""

    @abstractmethod
    def deploy(self, app, repo_dir: str, build_logs: List[str]) -> Dict[str, Any]:
        """Deploy the application into the target runtime (Docker, K8s, or Local)."""
        pass

    @abstractmethod
    def stop(self, app) -> bool:
        """Stop running instance of the application."""
        pass

    @abstractmethod
    def get_status(self, app) -> Dict[str, Any]:
        """Return runtime status for the application."""
        pass

    @abstractmethod
    def get_logs(self, app, max_lines: int = 200) -> List[str]:
        """Retrieve execution logs for the application."""
        pass

    @abstractmethod
    def get_live_url(self, app) -> str:
        """Return browser-accessible live URL for the application."""
        pass


class BaseDevDriver(ABC):
    """Abstract interface for managing interactive dev sandboxes with Omnigent AI integration."""

    @abstractmethod
    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str, workspace_folder: str = "", workspace_branch: str = "") -> Dict[str, Any]:
        """Start or attach to an interactive dev sandbox container or pod."""
        pass

    @abstractmethod
    def stop_dev(self, app) -> bool:
        """Stop the active dev sandbox."""
        pass

    @abstractmethod
    def get_dev_status(self, app) -> Dict[str, Any]:
        """Return runtime status of the dev sandbox."""
        pass

    @abstractmethod
    def get_dev_url(self, app) -> str:
        """Return preview URL for the dev sandbox."""
        pass

    @abstractmethod
    def get_dev_logs(self, app, max_lines: int = 200) -> str:
        """Return active stdout/stderr logs from the dev sandbox."""
        pass

    def exec_git_in_workspace(
        self,
        app,
        workspace_folder: str,
        commit_message: str,
        branch: str,
        auth_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute git operations inside the workspace (override in sub-drivers)."""
        return {"success": False, "error": "Not implemented for this driver"}

    def exec_command_in_dev(
        self,
        app,
        command: str,
        workspace_folder: str = "",
    ) -> Dict[str, Any]:
        """Execute a single shell command inside the dev container / pod workspace."""
        return {"success": False, "exit_code": 1, "output": "Not implemented for this driver"}

    def get_live_branch(self, app, workspace_folder: str = "") -> Optional[str]:
        """Fetch the active Git branch from inside the running dev workspace."""
        return None

    def open_terminal_ws_client(
        self,
        app,
        workspace_folder: str = "",
        cols: int = 80,
        rows: int = 24,
    ) -> Any:
        """Create a bidirectional streaming connection / PTY client to the dev pod / container."""
        return None

