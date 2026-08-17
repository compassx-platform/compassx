"""Projection handler registry.

Maps entity_name → ProjectionHandler instance.

Usage
-----
# Register a handler (done at module import time in each projections/*.py file):
from app.services.projection_registry import register
register(MyHandler())

# Dispatch (done by projection_service.sync_projection):
from app.services.projection_registry import get_handler
handler = get_handler("my_entity")
if handler:
    handler.sync(db, record)

Adding a new entity projection
-------------------------------
1. Create  backend/app/projections/<entity_name>.py
2. Implement ProjectionHandler ABC (see projections/base.py)
3. Add one import line in backend/app/main.py:
       import app.projections.<entity_name>  # noqa: F401
   That import triggers self-registration — zero changes to core services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.projections.base import ProjectionHandler

# Internal registry — module-level singleton dict
_REGISTRY: dict[str, "ProjectionHandler"] = {}


def register(handler: "ProjectionHandler") -> None:
    """Register a projection handler for an entity.

    Overwrites any previously registered handler for the same entity_name,
    which allows hot-reloading in development without errors.
    """
    _REGISTRY[handler.entity_name] = handler


def get_handler(entity_name: str) -> "ProjectionHandler | None":
    """Return the registered handler for *entity_name*, or None.

    A None return is NOT an error — it simply means no projection
    is configured for this entity.
    """
    return _REGISTRY.get(entity_name)


def registered_entities() -> list[str]:
    """Return a sorted list of entity names that have projection handlers."""
    return sorted(_REGISTRY.keys())