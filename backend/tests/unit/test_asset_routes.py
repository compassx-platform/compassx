from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_manager.routes import asset_type_routes
from app.database import get_asset_db


@pytest.fixture()
def asset_client(db_session) -> TestClient:
    app = FastAPI()

    def _override_get_asset_db():
        yield db_session

    app.dependency_overrides[get_asset_db] = _override_get_asset_db
    app.include_router(asset_type_routes.router)
    return TestClient(app)


def test_create_and_list_asset_type(asset_client):
    payload = {
        "name": "Centrifugal Pump",
        "slug": "centrifugal-pump",
        "category": "EQUIPMENT",
        "description": "Fluid transfer pump",
        "industry_tags": ["oil-gas", "water"],
        "icon": "pump-icon",
        "allowed_parents": [],
        "allowed_children": [],
        "metadata_schema": {
            "version": 1,
            "fields": [
                {
                    "key": "flow_rate",
                    "label": "Flow Rate",
                    "type": "FLOAT",
                    "required": False
                }
            ]
        },
        "is_root": True,
        "is_leaf": False
    }

    # Create Asset Type
    resp = asset_client.post("/api/v1/asset-types", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Centrifugal Pump"
    assert data["slug"] == "centrifugal-pump"
    assert data["category"] == "EQUIPMENT"

    # List Asset Types
    resp = asset_client.get("/api/v1/asset-types")
    assert resp.status_code == 200
    list_data = resp.json()
    assert len(list_data) == 1
    assert list_data[0]["name"] == "Centrifugal Pump"
    assert list_data[0]["slug"] == "centrifugal-pump"
