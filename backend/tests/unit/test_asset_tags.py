from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_manager.routes import asset_type_routes, asset_tag_routes, asset_instance_routes
from app.database import get_asset_db


@pytest.fixture()
def asset_client(db_session) -> TestClient:
    app = FastAPI()

    def _override_get_asset_db():
        yield db_session

    app.dependency_overrides[get_asset_db] = _override_get_asset_db
    app.include_router(asset_type_routes.router)
    app.include_router(asset_tag_routes.router)
    app.include_router(asset_instance_routes.router)
    return TestClient(app)


def test_asset_type_tag_definitions(asset_client):
    # 1. Create Asset Type with Tag Definitions
    payload = {
        "name": "Inverter",
        "slug": "inverter",
        "category": "EQUIPMENT",
        "description": "DC to AC power converter",
        "tag_definitions": [
            {
                "tag_key": "active_power",
                "name": "Active Power Output",
                "parameter": "Active Power",
                "unit": "kW",
                "is_required": True
            },
            {
                "tag_key": "efficiency",
                "name": "Conversion Efficiency",
                "parameter": "Efficiency",
                "unit": "%"
            }
        ]
    }
    resp = asset_client.post("/api/v1/asset-types", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    type_id = data["id"]
    assert len(data["tag_definitions"]) == 2
    assert data["tag_definitions"][0]["tag_key"] == "active_power"
    assert data["tag_definitions"][0]["is_required"] is True

    # 2. Get Asset Type Tag Definitions via Endpoint
    resp = asset_client.get(f"/api/v1/asset-types/{type_id}/tags")
    assert resp.status_code == 200
    tags = resp.json()
    assert len(tags) == 2
    assert tags[1]["tag_key"] == "efficiency"

    # 3. Create Tag Definition on Asset Type
    resp = asset_client.post(
        f"/api/v1/asset-types/{type_id}/tags",
        json={
            "tag_key": "temperature",
            "name": "Internal Temperature",
            "parameter": "Temperature",
            "unit": "C"
        }
    )
    assert resp.status_code == 201
    new_tag_def = resp.json()
    tag_def_id = new_tag_def["id"]

    # 4. Update Tag Definition
    resp = asset_client.put(
        f"/api/v1/asset-types/{type_id}/tags/{tag_def_id}",
        json={
            "name": "Cabinet Temperature",
            "unit": "F"
        }
    )
    assert resp.status_code == 200
    updated_tag_def = resp.json()
    assert updated_tag_def["name"] == "Cabinet Temperature"
    assert updated_tag_def["unit"] == "F"

    # 5. Delete Tag Definition
    resp = asset_client.delete(f"/api/v1/asset-types/{type_id}/tags/{tag_def_id}")
    assert resp.status_code == 204

    resp = asset_client.get(f"/api/v1/asset-types/{type_id}/tags")
    tags = resp.json()
    assert len(tags) == 2


def test_asset_tag_linking_and_autofill(asset_client):
    # 1. Create Asset Type with Tag Definitions
    payload = {
        "name": "Wind Turbine",
        "slug": "wind-turbine",
        "category": "EQUIPMENT",
        "tag_definitions": [
            {
                "tag_key": "wind_speed",
                "name": "Anemometer Wind Speed",
                "parameter": "Wind Speed",
                "unit": "m/s"
            }
        ]
    }
    resp = asset_client.post("/api/v1/asset-types", json=payload)
    type_id = resp.json()["id"]
    tag_def_id = resp.json()["tag_definitions"][0]["id"]

    # 2. Create Asset Instance
    instance_payload = {
        "asset_type_id": type_id,
        "name": "WTG 01",
        "code": "WTG01"
    }
    resp = asset_client.post("/api/v1/asset-instances", json=instance_payload)
    assert resp.status_code == 201
    asset_id = resp.json()["id"]

    # 3. Link Tag to Asset with asset_type_tag_id (autofill parameter & unit)
    tag_payload = {
        "asset_id": asset_id,
        "tag_id": "WTG01.ANEMOMETER.WS",
        "tag_name": "Turbine 1 Wind Speed",
        "asset_type_tag_id": tag_def_id
    }
    resp = asset_client.post("/api/v1/asset-tags", json=tag_payload)
    assert resp.status_code == 201
    tag_link = resp.json()
    assert tag_link["parameter"] == "Wind Speed"  # Autofilled
    assert tag_link["unit"] == "m/s"              # Autofilled
    assert tag_link["asset_type_tag_id"] == tag_def_id
    assert tag_link["asset_type_tag"]["tag_key"] == "wind_speed"

    # 4. Try linking a tag definition belonging to a different asset type
    payload_other = {
        "name": "Solar Panel",
        "slug": "solar-panel",
        "category": "EQUIPMENT",
        "tag_definitions": [
            {
                "tag_key": "irradiance",
                "name": "Solar Irradiance",
                "parameter": "Irradiance",
                "unit": "W/m2"
            }
        ]
    }
    resp_other = asset_client.post("/api/v1/asset-types", json=payload_other)
    other_tag_def_id = resp_other.json()["tag_definitions"][0]["id"]

    tag_payload_bad = {
        "asset_id": asset_id,
        "tag_id": "WTG01.SOLAR.IRR",
        "tag_name": "WTG Solar Irradiance",
        "asset_type_tag_id": other_tag_def_id
    }
    resp = asset_client.post("/api/v1/asset-tags", json=tag_payload_bad)
    assert resp.status_code == 422
    assert "Tag definition does not belong to the asset's type" in resp.json()["detail"]
