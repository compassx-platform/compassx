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
    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str) -> Dict[str, Any]:
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
    def get_dev_logs(self, app) -> str:
        """Return active stdout/stderr logs from the dev sandbox."""
        pass
