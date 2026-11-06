"""Portal routes: /api/v1/portal/...

Provides workspace-scoped portal navigation configuration, available items
(apps & dashboards) for sidebar customization, and layout persistence.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_system_db, get_account_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.models.dashboard import Dashboard
from app.models.portal_config import PortalConfig
from app.schemas.portal_config import (
    AvailableAppItem,
    AvailableDashboardItem,
    PortalAvailableItemsResponse,
    PortalConfigOut,
    PortalConfigUpdate,
    PortalItem,
    PortalSection,
)

logger = logging.getLogger("app.routes.portal_routes")
