"""
Integration tests for data catalog API routes

Coverage
--------
- POST   /api/v1/data-catalog/connections           — create connection
- GET    /api/v1/data-catalog/connections           — list connections
- GET    /api/v1/data-catalog/connections/{id}      — get connection
- PUT    /api/v1/data-catalog/connections/{id}      — update connection
- DELETE /api/v1/data-catalog/connections/{id}      — delete connection
- POST   /api/v1/data-catalog/connections/test      — test connection
- GET    /api/v1/data-catalog/{id}/databases        — list databases
- GET    /api/v1/data-catalog/{id}/databases/{db}/schemas — list schemas
- GET    /api/v1/data-catalog/{id}/databases/{db}/schemas/{s}/tables — list tables
- POST   /api/v1/data-catalog/sql/execute           — execute SQL
- HTTP 404 / 422 error responses
- Password never exposed in responses
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Connection CRUD Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateConnectionRoute:

    def test_create_connection_returns_201(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "Test DB",
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": "secret",
                "default_database": "testdb",
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_create_connection_returns_integer_id(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "Integer ID DB",
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": "secret",
                "default_database": "testdb",
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_create_connection_does_not_expose_password(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "Secure DB",
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": "my_secret_password",
                "default_database": "testdb",
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        # Response must not contain plaintext password
        assert "password" not in data
        assert "password_enc" not in data
        assert "my_secret_password" not in str(data)

    def test_create_connection_stores_correct_metadata(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "Metadata DB",
                "host": "db.example.com",
                "port": 5433,
                "username": "admin",
                "password": "pass",
                "default_database": "analytics",
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert data["name"] == "Metadata DB"
        assert data["host"] == "db.example.com"
        assert data["port"] == 5433
        assert data["username"] == "admin"
        assert data["default_database"] == "analytics"

    def test_create_connection_missing_name_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={"host": "localhost", "username": "user", "password": "pass"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422

    def test_create_connection_invalid_port_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "Bad Port",
                "host": "localhost",
                "port": 99999,
                "username": "user",
                "password": "pass",
                "default_database": "db",
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


class TestListConnectionsRoute:

    def test_list_connections_returns_200(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            "/api/v1/data-catalog/connections",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_list_connections_returns_list(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            "/api/v1/data-catalog/connections",
            headers={"authkey": "test-key"},
        )
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_connections_have_integer_ids(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            "/api/v1/data-catalog/connections",
            headers={"authkey": "test-key"},
        )
        for conn in resp.json():
            assert isinstance(conn["id"], int)

    def test_list_connections_no_passwords_exposed(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            "/api/v1/data-catalog/connections",
            headers={"authkey": "test-key"},
        )
        for conn in resp.json():
            assert "password" not in conn
            assert "password_enc" not in conn


class TestGetConnectionRoute:

    def test_get_connection_returns_200(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_get_connection_returns_integer_id(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            headers={"authkey": "test-key"},
        )
        assert isinstance(resp.json()["id"], int)

    def test_get_connection_not_found_returns_404(self, client: TestClient):
        resp = client.get(
            "/api/v1/data-catalog/connections/999999",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_get_connection_no_password_exposed(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.get(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert "password" not in data
        assert "password_enc" not in data


class TestUpdateConnectionRoute:

    def test_update_connection_returns_200(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.put(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            json={"name": "Updated Connection Name"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_update_connection_changes_name(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.put(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            json={"name": "New Name"},
            headers={"authkey": "test-key"},
        )
        assert resp.json()["name"] == "New Name"

    def test_update_connection_not_found_returns_404(self, client: TestClient):
        resp = client.put(
            "/api/v1/data-catalog/connections/999999",
            json={"name": "Ghost"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_update_connection_invalid_port_returns_422(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.put(
            f"/api/v1/data-catalog/connections/{sample_catalog_connection.id}",
            json={"port": 99999},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


class TestDeleteConnectionRoute:

    def test_delete_connection_returns_204(self, client: TestClient):
        # Create a connection to delete
        create_resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "To Delete",
                "host": "localhost",
                "port": 5432,
                "username": "user",
                "password": "pass",
                "default_database": "db",
            },
            headers={"authkey": "test-key"},
        )
        conn_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/v1/data-catalog/connections/{conn_id}",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 204

    def test_delete_connection_removes_from_list(self, client: TestClient):
        create_resp = client.post(
            "/api/v1/data-catalog/connections",
            json={
                "name": "To Delete 2",
                "host": "localhost",
                "port": 5432,
                "username": "user",
                "password": "pass",
                "default_database": "db",
            },
            headers={"authkey": "test-key"},
        )
        conn_id = create_resp.json()["id"]
        client.delete(
            f"/api/v1/data-catalog/connections/{conn_id}",
            headers={"authkey": "test-key"},
        )
        get_resp = client.get(
            f"/api/v1/data-catalog/connections/{conn_id}",
            headers={"authkey": "test-key"},
        )
        assert get_resp.status_code == 404

    def test_delete_connection_not_found_returns_404(self, client: TestClient):
        resp = client.delete(
            "/api/v1/data-catalog/connections/999999",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Connection Test Route
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionTestRoute:

    @patch("app.services.data_catalog_service.psycopg2.connect")
    def test_test_connection_success_returns_200(self, mock_connect, client: TestClient):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 15.0",)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        resp = client.post(
            "/api/v1/data-catalog/connections/test",
            json={
                "host": "localhost",
                "port": 5432,
                "username": "user",
                "password": "pass",
                "database": "testdb",
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.services.data_catalog_service.psycopg2.connect")
    def test_test_connection_failure_returns_200_with_error(
        self, mock_connect, client: TestClient
    ):
        import psycopg2
        mock_connect.side_effect = psycopg2.OperationalError("Connection refused")

        resp = client.post(
            "/api/v1/data-catalog/connections/test",
            json={
                "host": "bad-host",
                "port": 5432,
                "username": "user",
                "password": "pass",
                "database": "testdb",
            },
            headers={"authkey": "test-key"},
        )
        # Returns 200 with success=False (not a 500)
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_test_connection_missing_host_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/connections/test",
            json={"port": 5432, "username": "user", "password": "pass", "database": "db"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Catalog Browsing Routes (mocked psycopg2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCatalogBrowsingRoutes:

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_databases_returns_200(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"name": "postgres", "owner": "postgres"},
            {"name": "analytics", "owner": "admin"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.get(
            f"/api/v1/data-catalog/{sample_catalog_connection.id}/databases",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_databases_returns_list(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"name": "postgres", "owner": "postgres"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.get(
            f"/api/v1/data-catalog/{sample_catalog_connection.id}/databases",
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert "databases" in data
        assert isinstance(data["databases"], list)

    def test_list_databases_connection_not_found_returns_404(self, client: TestClient):
        resp = client.get(
            "/api/v1/data-catalog/999999/databases",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_schemas_returns_200(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"name": "public", "owner": "postgres"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.get(
            f"/api/v1/data-catalog/{sample_catalog_connection.id}/databases/testdb/schemas",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_tables_returns_200(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"name": "users", "schema_name": "public", "table_type": "BASE TABLE", "row_estimate": 100}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.get(
            f"/api/v1/data-catalog/{sample_catalog_connection.id}/databases/testdb/schemas/public/tables",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SQL Execute Route
# ═══════════════════════════════════════════════════════════════════════════════


class TestSqlExecuteRoute:

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_returns_200(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={
                "connection_id": sample_catalog_connection.id,
                "database": "testdb",
                "sql": "SELECT id, name FROM users",
                "limit": 100,
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_returns_columns_and_rows(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={
                "connection_id": sample_catalog_connection.id,
                "database": "testdb",
                "sql": "SELECT id, name FROM users",
                "limit": 100,
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert "columns" in data
        assert "rows" in data
        assert data["columns"] == ["id", "name"]
        assert data["row_count"] == 2

    def test_execute_sql_connection_not_found_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={
                "connection_id": 999999,
                "database": "testdb",
                "sql": "SELECT 1",
                "limit": 100,
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_execute_sql_missing_sql_returns_422(
        self, client: TestClient, sample_catalog_connection
    ):
        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={
                "connection_id": sample_catalog_connection.id,
                "database": "testdb",
                "sql": "",
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422

    def test_execute_sql_missing_connection_id_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={"database": "testdb", "sql": "SELECT 1"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_limit_exceeded_returns_422(
        self, mock_conn_from_record, client: TestClient, sample_catalog_connection
    ):
        resp = client.post(
            "/api/v1/data-catalog/sql/execute",
            json={
                "connection_id": sample_catalog_connection.id,
                "database": "testdb",
                "sql": "SELECT 1",
                "limit": 999999,  # exceeds max
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422