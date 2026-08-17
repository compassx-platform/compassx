from __future__ import annotations

from typing import Any

from app.asset_manager.schemas.agent_context import AssetManagerContextRequest


class AssetManagerContextResolver:
    """Resolves frontend Asset Manager context for agent/Nova tool usage."""

    def resolve(self, payload: AssetManagerContextRequest) -> dict[str, Any]:
        selected = []
        if payload.selected_asset_id:
            selected.append(f"asset #{payload.selected_asset_id}")
        if payload.selected_asset_type_id:
            selected.append(f"asset type #{payload.selected_asset_type_id}")

        return {
            "summary": self._build_summary(payload, selected),
            "asset_manager": {
                "route": payload.route,
                "mode": payload.mode,
                "selected_asset_id": payload.selected_asset_id,
                "selected_asset_type_id": payload.selected_asset_type_id,
            },
            "filters": payload.filters,
            "view_state": payload.view_state,
        }

    def _build_summary(self, payload: AssetManagerContextRequest, selected: list[str]) -> str:
        selection = ", ".join(selected) if selected else "no selected asset"
        mode = payload.mode or "unknown"
        route = payload.route or "unknown"
        return f"Asset Manager context is active on {route} in {mode} mode with {selection}."

