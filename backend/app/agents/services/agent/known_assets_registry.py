"""Known-Assets Registry — Part G1 of AI Data Engineer Spec v5.

Session-scoped, in-memory registry of every platform asset (table, notebook,
dashboard, volume, job, app) that has appeared in a real tool result during
the current chat session.

Populated at tool-call time by the orchestrator.  The UI uses this to resolve
<asset> tags emitted by the model into clickable chips (G2–G4).  When a plan
step is active, mirrored into plan.steps[].assets_touched (D17).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AssetEntry:
    full_name: str          # catalog.schema.object
    object_type: str        # notebook | table | dashboard | volume | job | app | query
    first_seen_turn: int
    source: str             # "tool_result" | "uploaded_document"
    action: str             # "referenced" | "created" | "modified"
    plan_id: Optional[str] = None   # set only when turn is part of an active plan


class KnownAssetsRegistry:
    """Thread-safe, session-scoped in-memory registry.

    One singleton per process; keyed by (session_id, full_name).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # {session_id: {full_name: AssetEntry}}
        self._data: Dict[int, Dict[str, AssetEntry]] = {}
        # {session_id: int}  — current turn counter per session
        self._turn_counter: Dict[int, int] = {}

    # ── Turn tracking ─────────────────────────────────────────────────────────

    def increment_turn(self, session_id: int) -> int:
        with self._lock:
            self._turn_counter[session_id] = self._turn_counter.get(session_id, 0) + 1
            return self._turn_counter[session_id]

    def current_turn(self, session_id: int) -> int:
        return self._turn_counter.get(session_id, 0)

    # ── Registration ──────────────────────────────────────────────────────────

    def register(
        self,
        session_id: int,
        full_name: str,
        object_type: str,
        source: str = "tool_result",
        action: str = "referenced",
        plan_id: Optional[str] = None,
    ) -> AssetEntry:
        with self._lock:
            if session_id not in self._data:
                self._data[session_id] = {}
            existing = self._data[session_id].get(full_name)
            if existing:
                # Upgrade action if more significant
                _rank = {"referenced": 0, "created": 1, "modified": 2}
                if _rank.get(action, 0) > _rank.get(existing.action, 0):
                    existing.action = action
                if plan_id and not existing.plan_id:
                    existing.plan_id = plan_id
                return existing

            entry = AssetEntry(
                full_name=full_name,
                object_type=object_type,
                first_seen_turn=self._turn_counter.get(session_id, 0),
                source=source,
                action=action,
                plan_id=plan_id,
            )
            self._data[session_id][full_name] = entry
            return entry

    def resolve(self, session_id: int, full_name: str) -> Optional[AssetEntry]:
        with self._lock:
            return self._data.get(session_id, {}).get(full_name)

    def get_all(self, session_id: int) -> List[AssetEntry]:
        with self._lock:
            return list(self._data.get(session_id, {}).values())

    def clear_session(self, session_id: int) -> None:
        with self._lock:
            self._data.pop(session_id, None)
            self._turn_counter.pop(session_id, None)


# Process-level singleton — imported by orchestrator
registry = KnownAssetsRegistry()


# ── Tool-result scanner ───────────────────────────────────────────────────────

# Catalog/file/notebook tools whose results contain full_name references
_CATALOG_TOOLS = {
    "search_assets", "search_catalog_metadata", "list_tables", "get_table_schema",
    "get_column_stats", "db_explorer", "asset_manager", "notebook_manager",
    "dashboard_manager", "create_notebook", "catalog_editor",
}

_ACTION_MAP = {
    "create": "created",
    "write": "modified",
    "update": "modified",
    "edit": "modified",
    "register": "created",
    "delete": "modified",
}


def _infer_action(tool_name: str) -> str:
    for verb, action in _ACTION_MAP.items():
        if verb in tool_name.lower():
            return action
    return "referenced"


def register_from_tool_result(
    session_id: int,
    tool_name: str,
    result: dict,
    plan_id: Optional[str] = None,
) -> None:
    """Extract asset references from a tool result and register them."""
    action = _infer_action(tool_name)
    _extract_and_register(session_id, result, action, plan_id)


def _extract_and_register(
    session_id: int,
    obj: object,
    action: str,
    plan_id: Optional[str],
) -> None:
    """Recursively walk result dicts/lists looking for full_name + object_type pairs."""
    if isinstance(obj, dict):
        full_name = (
            obj.get("full_name") or
            obj.get("path") or
            obj.get("notebook_path") or
            obj.get("asset_name")
        )
        if not (full_name and isinstance(full_name, str) and "." in full_name):
            cat = obj.get("catalog_name") or obj.get("catalog")
            sch = obj.get("schema_name") or obj.get("schema")
            name = obj.get("notebook_name") or obj.get("table_name") or (obj.get("name") if not (isinstance(obj.get("name"), str) and "." in str(obj.get("name"))) else None)
            if cat and sch and name and isinstance(cat, str) and isinstance(sch, str) and isinstance(name, str):
                full_name = f"{cat}.{sch}.{name}"
            elif obj.get("name") and isinstance(obj.get("name"), str) and "." in str(obj.get("name")):
                full_name = str(obj.get("name"))

        object_type = obj.get("object_type") or obj.get("type") or obj.get("asset_type")
        if not object_type:
            if "notebook" in str(full_name).lower() or obj.get("notebook_id"):
                object_type = "notebook"
            elif "table" in str(full_name).lower() or obj.get("table_name"):
                object_type = "table"
            else:
                object_type = "unknown"

        if full_name and isinstance(full_name, str) and "." in full_name:
            registry.register(
                session_id=session_id,
                full_name=full_name,
                object_type=str(object_type),
                source="tool_result",
                action=action,
                plan_id=plan_id,
            )
        for v in obj.values():
            _extract_and_register(session_id, v, action, plan_id)
    elif isinstance(obj, list):
        for item in obj:
            _extract_and_register(session_id, item, action, plan_id)
