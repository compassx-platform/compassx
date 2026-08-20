"""Base classes and contracts for Connection Providers (SOLID Open/Closed Principle)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ConnectionFieldDefinition:
    """Descriptor for a configuration or authentication input field rendered in UI."""

    name: str
    label: str
    type: str = "text"  # text | password | number | boolean | select | textarea
    required: bool = True
    default: Any = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[dict[str, str]]] = None  # for select type: [{"value": "x", "label": "X"}]


@dataclass
class ConnectionTestResult:
    """Standardized test result returned when verifying a connection."""

    success: bool
    message: str
    latency_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class BaseConnectionProvider(ABC):
    """Abstract connection provider contract.

    Follows SOLID principles:
    - Single Responsibility: Manages connection building, testing, and field descriptors for a single connector type.
    - Open/Closed: New providers can be plugged into the registry without modifying core code.
    """

    @property
    @abstractmethod
    def type_id(self) -> str:
        """Unique identifier, e.g. 'postgres', 'rest_api', 'loki'."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'PostgreSQL Database'."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: 'database' | 'api' | 'observability' | 'custom'."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short summary of the connector."""
        pass

    @property
    def is_popular(self) -> bool:
        """Whether to feature this provider in the popular connectors banner."""
        return False

    @property
    def logo(self) -> str:
        """Brand identifier for frontend logo rendering."""
        return self.type_id

    @property
    def default_port(self) -> Optional[int]:
        """Default port number if applicable."""
        return None

    @property
    @abstractmethod
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        """Non-sensitive connection configuration fields (host, port, db_name, base_url)."""
        pass

    @property
    @abstractmethod
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        """Sensitive authentication fields (passwords, tokens, API keys)."""
        pass

    @abstractmethod
    def test_connection(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionTestResult:
        """Test live connectivity using the given configuration and credentials."""
        pass

    def build_client(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Build runtime client (e.g. ConnectionClient, HTTP client, or SDK handle)."""
        raise NotImplementedError(f"Provider {self.type_id} does not support build_client()")

    def build_engine(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Build SQLAlchemy Engine for database connectors."""
        raise NotImplementedError(f"Provider {self.type_id} does not support build_engine()")
