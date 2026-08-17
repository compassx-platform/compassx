from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssetManagerContextRequest(BaseModel):
    route: str | None = None
    mode: str | None = None
    selected_asset_id: int | None = Field(default=None, ge=1)
    selected_asset_type_id: int | None = Field(default=None, ge=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    view_state: dict[str, Any] = Field(default_factory=dict)

