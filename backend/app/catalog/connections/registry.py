"""Connection Provider Registry and Factory (SOLID Open/Closed Principle)."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.catalog.connections.base_provider import BaseConnectionProvider
from app.catalog.connections.providers.sql_providers import (
    PostgresProvider,
    MySQLProvider,
    MSSQLProvider,
    SnowflakeProvider,
    SQLiteProvider,
    OracleProvider,
    BigQueryProvider,
    DatabricksProvider,
)
from app.catalog.connections.providers.api_providers import (
    RestApiProvider,
    CustomWebhookProvider,
)
from app.catalog.connections.providers.observability_providers import (
    LokiProvider,
    PrometheusProvider,
)

logger = logging.getLogger(__name__)


class ConnectionProviderRegistry:
    """Registry maintaining all available connection providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseConnectionProvider] = {}

    def register(self, provider: BaseConnectionProvider) -> None:
        """Register a new or custom provider."""
        self._providers[provider.type_id] = provider
        logger.debug("Registered connection provider '%s' (%s)", provider.type_id, provider.name)

    def get(self, type_id: str) -> Optional[BaseConnectionProvider]:
        """Get provider by type_id, or None if not found."""
        return self._providers.get(type_id)

    def get_required(self, type_id: str) -> BaseConnectionProvider:
        """Get provider by type_id or raise ValueError."""
        provider = self._providers.get(type_id)
        if not provider:
            raise ValueError(f"Unsupported connector type: '{type_id}'. Available: {list(self._providers.keys())}")
        return provider

    def list_all(self) -> List[BaseConnectionProvider]:
        """List all registered providers."""
        return list(self._providers.values())

    def list_popular(self) -> List[BaseConnectionProvider]:
        """List providers marked as popular."""
        return [p for p in self._providers.values() if p.is_popular]

    def list_by_category(self, category: str) -> List[BaseConnectionProvider]:
        """List providers by category."""
        return [p for p in self._providers.values() if p.category == category]


# Global singleton registry
registry = ConnectionProviderRegistry()

# Register built-in SQL database providers
registry.register(PostgresProvider())
registry.register(MySQLProvider())
registry.register(MSSQLProvider())
registry.register(SnowflakeProvider())
registry.register(SQLiteProvider())
registry.register(OracleProvider())
registry.register(BigQueryProvider())
registry.register(DatabricksProvider())

# Register API and Webhook providers
registry.register(RestApiProvider())
registry.register(CustomWebhookProvider())

# Register Observability providers
registry.register(LokiProvider())
registry.register(PrometheusProvider())


def get_provider(type_id: str) -> BaseConnectionProvider:
    return registry.get_required(type_id)


def list_providers(category: Optional[str] = None) -> List[BaseConnectionProvider]:
    if category:
        return registry.list_by_category(category)
    return registry.list_all()
