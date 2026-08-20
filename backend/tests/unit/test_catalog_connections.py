"""Unit and integration tests for First-Class Catalog Connections."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.catalog.models import UnifiedCatalogConnection
from app.catalog.connections.registry import registry, get_provider, list_providers
from app.catalog.connections.service import connection_service
from app.catalog.connections.schemas import (
    CatalogConnectionCreate,
    CatalogConnectionUpdate,
    ConnectionTestRequest,
)
import services.compassx_tools as cx


# ── 1. Provider Registry Tests (SOLID Open/Closed Principle) ─────────────────

def test_provider_registry_builtins():
    # Verify SQL providers
    pg = get_provider("postgres")
    assert pg.name == "PostgreSQL"
    assert pg.category == "database"
    assert pg.is_popular is True
    assert pg.default_port == 5432
    assert any(f.name == "host" for f in pg.config_fields)
    assert any(f.name == "password" for f in pg.auth_fields)

    mysql = get_provider("mysql")
    assert mysql.name == "MySQL"
    assert mysql.category == "database"
    assert mysql.is_popular is True

    snowflake = get_provider("snowflake")
    assert snowflake.name == "Snowflake"
    assert snowflake.category == "database"

    # Verify API providers
    rest = get_provider("rest_api")
    assert rest.name == "REST API"
    assert rest.category == "api"
    assert rest.is_popular is True
    assert any(f.name == "base_url" for f in rest.config_fields)

    # Verify Observability providers
    loki = get_provider("loki")
    assert loki.name == "Grafana Loki"
    assert loki.category == "observability"
    assert loki.is_popular is True

    prom = get_provider("prometheus")
    assert prom.name == "Prometheus"
    assert prom.category == "observability"

    # Category filters
    db_providers = list_providers("database")
    assert len(db_providers) >= 5
    api_providers = list_providers("api")
    assert len(api_providers) >= 2


# ── 2. Catalog Connection CRUD & Encryption Tests ────────────────────────────

def test_catalog_connection_crud_and_encryption(db_session: Session):
    payload = CatalogConnectionCreate(
        catalog="analytics",
        schema="dw",
        name="prod_postgres",
        connector_type="postgres",
        description="Main DW analytics database",
        config={"host": "dw.internal", "port": 5432, "database": "dw_db"},
        auth_config={"username": "dw_user", "password": "super-secret-password"},
        status="active",
    )

    # 1. Create
    conn = connection_service.create_connection(db_session, payload, user_id="user_admin")
    assert conn.id is not None
    assert conn.catalog_name == "analytics"
    assert conn.schema_name == "dw"
    assert conn.name == "prod_postgres"
    assert conn.category == "database"
    assert conn.connector_type == "postgres"

    # Verify encryption at rest (password not in plaintext in auth_config column)
    assert conn.auth_config is not None
    assert "super-secret-password" not in conn.auth_config

    # Decrypt server-side
    decrypted = connection_service.get_decrypted_auth_config(conn)
    assert isinstance(decrypted, dict)
    assert decrypted["username"] == "dw_user"
    assert decrypted["password"] == "super-secret-password"

    # 2. Get by UUID and by 3-part FQN
    found_by_id = connection_service.get_connection(db_session, conn.id)
    assert found_by_id is not None
    assert found_by_id.name == "prod_postgres"

    found_by_fqn = connection_service.get_connection(db_session, "analytics.dw.prod_postgres")
    assert found_by_fqn is not None
    assert found_by_fqn.id == conn.id

    # 3. List
    conns = connection_service.list_connections(db_session, catalog_name="analytics")
    assert len(conns) >= 1
    assert any(c.id == conn.id for c in conns)

    # List with search
    searched = connection_service.list_connections(db_session, search_query="DW analytics")
    assert len(searched) >= 1

    # 4. Update
    updated = connection_service.update_connection(
        db_session,
        conn.id,
        CatalogConnectionUpdate(
            description="Updated DW description",
            config={"host": "dw-replica.internal", "port": 5432, "database": "dw_db"},
        ),
    )
    assert updated is not None
    assert updated.description == "Updated DW description"
    assert updated.config["host"] == "dw-replica.internal"

    # 5. Toggle status
    toggled = connection_service.toggle_status(db_session, conn.id)
    assert toggled.status == "disabled"
    toggled2 = connection_service.toggle_status(db_session, conn.id)
    assert toggled2.status == "active"

    # 6. Delete
    deleted = connection_service.delete_connection(db_session, conn.id)
    assert deleted is True
    assert connection_service.get_connection(db_session, conn.id) is None


# ── 3. Connection Live Testing ───────────────────────────────────────────────

def test_sql_connection_testing(db_session: Session):
    # Test SQLite connection (live test with in-memory DB)
    req = ConnectionTestRequest(
        connector_type="sqlite",
        config={"database": ":memory:"},
        auth_config={},
    )
    res = connection_service.test_connection(db_session, req)
    assert res.success is True
    assert "Successfully connected" in res.message


def test_rest_connection_testing(db_session: Session):
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    req = ConnectionTestRequest(
        connector_type="rest_api",
        config={"base_url": "https://api.example.com/v1"},
        auth_config={"auth_type": "bearer", "token": "tok123"},
    )

    with patch("httpx.Client.get", return_value=mock_resp):
        res = connection_service.test_connection(db_session, req)
        assert res.success is True
        assert "Connected to" in res.message


def test_loki_connection_testing(db_session: Session):
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    req = ConnectionTestRequest(
        connector_type="loki",
        config={"base_url": "http://loki:3100", "org_id": "tenant1"},
        auth_config={"token": "tok123"},
    )

    with patch("httpx.Client.get", return_value=mock_resp):
        res = connection_service.test_connection(db_session, req)
        assert res.success is True
        assert "Loki server is ready" in res.message


# ── 4. API Endpoints ──────────────────────────────────────────────────────────

def test_catalog_connection_api_endpoints(client: TestClient):
    # 1. GET /api/v1/connections/providers
    res_prov = client.get("/api/v1/connections/providers")
    assert res_prov.status_code == 200
    providers = res_prov.json()
    assert len(providers) >= 8
    assert any(p["type_id"] == "postgres" for p in providers)
    assert any(p["type_id"] == "rest_api" for p in providers)

    # 2. POST /api/v1/connections (Create)
    res_create = client.post(
        "/api/v1/connections",
        json={
            "catalog": "main",
            "schema": "default",
            "name": "api_rest_test",
            "connector_type": "rest_api",
            "description": "Test REST connection via API",
            "config": {"base_url": "https://httpbin.org"},
            "auth_config": {"auth_type": "bearer", "token": "secret_abc"},
            "status": "active",
        },
    )
    assert res_create.status_code == 201
    data = res_create.json()
    assert data["name"] == "api_rest_test"
    assert data["connector_type"] == "rest_api"
    conn_id = data["id"]
    # Ensure sensitive auth_config is NOT in response
    assert "auth_config" not in data

    # 3. GET /api/v1/connections (List)
    res_list = client.get("/api/v1/connections")
    assert res_list.status_code == 200
    items = res_list.json()
    assert any(i["id"] == conn_id for i in items)

    # 4. GET /api/v1/connections/{id}
    res_get = client.get(f"/api/v1/connections/{conn_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "api_rest_test"

    # 5. POST /api/v1/connections/test (Saved Connection Test)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.Client.get", return_value=mock_resp):
        res_test = client.post("/api/v1/connections/test", json={"connection_id": conn_id})
        assert res_test.status_code == 200
        assert res_test.json()["success"] is True

    # 6. POST /api/v1/connections/{id}/toggle-status
    res_tog = client.post(f"/api/v1/connections/{conn_id}/toggle-status")
    assert res_tog.status_code == 200
    assert res_tog.json()["status"] == "disabled"

    # 7. DELETE /api/v1/connections/{id}
    res_del = client.delete(f"/api/v1/connections/{conn_id}")
    assert res_del.status_code == 204


# ── 5. SDK Connection Resolution Tests ───────────────────────────────────────

def test_sdk_catalog_connection_resolution(db_session: Session):
    conn = connection_service.create_connection(
        db_session,
        CatalogConnectionCreate(
            catalog="main",
            schema="default",
            name="loki_sdk_test",
            connector_type="loki",
            config={"base_url": "http://loki:3100", "org_id": "tenant1"},
            auth_config={"token": "tok123"},
        ),
    )

    # Simulate environment injection (as done by external_tool_executor)
    cx.connections.register(
        name="main.default.loki_sdk_test",
        base_url="http://loki:3100",
        auth_config={"token": "tok123"},
        connector_type="loki",
    )

    # Resolve by FQN
    resolved_fqn = cx.connections.get("main.default.loki_sdk_test")
    assert resolved_fqn is not None
    assert resolved_fqn.base_url == "http://loki:3100"

    # Resolve by short name
    resolved_short = cx.connections.get("loki_sdk_test")
    assert resolved_short is not None
    assert resolved_short.base_url == "http://loki:3100"


def test_account_level_connection_creation(db_session: Session, client: TestClient):
    # 1. Create account-level connection without catalog/schema
    payload = {
        "name": "global_stripe_api",
        "connector_type": "rest_api",
        "category": "api",
        "config": {"base_url": "https://api.stripe.com"},
        "auth_config": {"api_key": "sk_test_12345"},
    }
    res = client.post("/api/v1/connections", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "global_stripe_api"
    assert data["catalog"] is None
    assert data["schema_name"] is None
    assert data["full_name"] == "global_stripe_api"

    # 2. Query list
    res_list = client.get("/api/v1/connections")
    assert res_list.status_code == 200
    items = res_list.json()
    assert any(c["name"] == "global_stripe_api" for c in items)

    # 3. Clean up
    client.delete(f"/api/v1/connections/{data['id']}")
