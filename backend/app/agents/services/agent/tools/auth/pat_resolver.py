"""PAT (Personal Access Token) resolver — single source of truth.

Resolves a provider token by first checking the agent's configured
git connections (decrypted from the database), then falling back to
environment variables:
  - azure_devops → ADO_PAT
  - github       → GITHUB_TOKEN
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def get_pat(agent, provider: str) -> str:
    """Return the PAT for *provider*, or an empty string if none is found.

    Args:
        agent: An ``Agent`` ORM instance (or ``None``).
        provider: ``"github"`` or ``"azure_devops"``.
    """
    from app.services.encryption import decrypt_field

    if agent and getattr(agent, "git_connections", None):
        for agc in agent.git_connections:
            gc = getattr(agc, "git_connection", None)
            if gc is None:
                continue
            gc_provider = str(gc.provider).lower().strip()
            want_provider = str(provider).lower().strip()
            logger.debug(
                "get_pat: checking git_connection id=%s provider='%s' vs want='%s' has_pat=%s",
                getattr(gc, "id", "?"),
                gc_provider,
                want_provider,
                bool(getattr(gc, "pat_enc", None)),
            )
            if gc_provider == want_provider and getattr(gc, "pat_enc", None):
                pat = decrypt_field(gc.pat_enc)
                logger.debug("get_pat: found PAT in git_connection for provider=%s", provider)
                return pat

    # Fallback to env vars
    if provider == "azure_devops":
        pat = os.environ.get("ADO_PAT", "")
        logger.debug("get_pat: ADO_PAT from env = %s", "set" if pat else "NOT SET")
        return pat

    pat = os.environ.get("GITHUB_TOKEN", "")
    logger.debug("get_pat: GITHUB_TOKEN from env = %s", "set" if pat else "NOT SET")
    return pat
