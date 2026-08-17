"""Provider registry — maps provider name strings to GitProvider instances.

To add a new provider:
  1. Create a new module implementing GitProvider.
  2. Add it to _PROVIDERS below.
  No other files need to change.
"""

from __future__ import annotations

from app.agents.services.agent.tools.providers.base_provider import GitProvider
from app.agents.services.agent.tools.providers.github_provider import GitHubProvider
from app.agents.services.agent.tools.providers.ado_provider import AzureDevOpsProvider

_PROVIDERS: dict[str, GitProvider] = {
    "github": GitHubProvider(),
    "azure_devops": AzureDevOpsProvider(),
}


def get_provider(name: str) -> GitProvider:
    """Return the GitProvider for *name*.

    Raises ``ValueError`` for unknown providers so callers get a clear message
    instead of an ``AttributeError`` deep in dispatch code.
    """
    provider = _PROVIDERS.get(str(name).lower().strip())
    if provider is None:
        raise ValueError(
            f"Unsupported git provider: '{name}'. "
            f"Supported: {list(_PROVIDERS)}"
        )
    return provider


__all__ = ["GitProvider", "get_provider"]
