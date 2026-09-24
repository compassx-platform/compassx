from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class PortalItem(BaseModel):
    id: str = Field(..., description="Unique identifier for the portal navigation item")
    type: Literal["app", "dashboard", "external_link"] = Field(..., description="Type of target object")
    target_id: str = Field(..., description="ID or slug of the app, dashboard UUID, or unique link identifier")
    title: str = Field(..., description="Display label in the sidebar navigation")
    icon: Optional[str] = Field(None, description="Optional icon name override (e.g., LayoutGrid, BarChart2, Globe, etc.)")
    is_visible: bool = Field(True, description="Whether this item is visible to end users in the portal sidebar")
    order: int = Field(0, description="Display sorting order within the section")
    url: Optional[str] = Field(None, description="Optional URL override for apps or external links")
    app_type: Optional[str] = Field(None, description="Application framework type if type is app (e.g., streamlit, react, fastline)")
    status: Optional[str] = Field(None, description="Runtime status of the underlying app or dashboard")


class PortalSection(BaseModel):
    id: str = Field(..., description="Unique section identifier")
    title: str = Field(..., description="Section title / category name (e.g., 'Operations', 'Dashboards')")
    items: List[PortalItem] = Field(default_factory=list, description="List of items in this section")


class PortalConfigOut(BaseModel):
    id: Optional[str] = None
    workspace_id: str
    workspace_slug: Optional[str] = None
    sections: List[PortalSection] = Field(default_factory=list)
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PortalConfigUpdate(BaseModel):
    sections: List[PortalSection] = Field(..., description="Updated structured sections and items")


class AvailableAppItem(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    app_type: str
    status: str
    route: str


class AvailableDashboardItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_draft: bool
    published_at: Optional[datetime] = None


class PortalAvailableItemsResponse(BaseModel):
    apps: List[AvailableAppItem] = Field(default_factory=list)
    dashboards: List[AvailableDashboardItem] = Field(default_factory=list)
