"""
Unit tests for Pydantic schemas

Coverage
--------
- ConnectionCreate / ConnectionUpdate / SqlExecuteRequest validation
- Edge cases: empty strings, out-of-range values, missing required fields
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.data_catalog import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionTestRequest,
    SqlExecuteRequest,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectionCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionCreate:

    def test_valid_connection_create(self):
        conn = ConnectionCreate(
            name="My DB",
            host="db.example.com",
            port=5432,
            username="admin",
            password="secret",
            default_database="mydb",
        )
        assert conn.name == "My DB"
        assert conn.port == 5432

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="",
                host="localhost",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_host_required(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_port_must_be_positive(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="localhost",
                port=0,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_port_must_be_at_most_65535(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="localhost",
                port=65536,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_default_port_is_5432(self):
        conn = ConnectionCreate(
            name="DB",
            host="localhost",
            username="user",
            password="pass",
            default_database="db",
        )
        assert conn.port == 5432

    def test_default_database_defaults_to_postgres(self):
        conn = ConnectionCreate(
            name="DB",
            host="localhost",
            username="user",
            password="pass",
        )
        assert conn.default_database == "postgres"


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectionUpdate
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionUpdate:

    def test_all_fields_optional(self):
        update = ConnectionUpdate()
        assert update.name is None
        assert update.host is None
        assert update.password is None

    def test_partial_update_name(self):
        update = ConnectionUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.host is None

    def test_port_validation_in_update(self):
        with pytest.raises(ValidationError):
            ConnectionUpdate(port=99999)


# ═══════════════════════════════════════════════════════════════════════════════
# SqlExecuteRequest
# ═══════════════════════════════════════════════════════════════════════════════


class TestSqlExecuteRequest:

    def test_valid_sql_execute_request(self):
        req = SqlExecuteRequest(
            connection_id=1,
            database="mydb",
            sql="SELECT 1",
            limit=1000,
        )
        assert req.connection_id == 1
        assert req.sql == "SELECT 1"
        assert req.limit == 1000

    def test_connection_id_must_be_integer(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id="not-an-int",
                database="mydb",
                sql="SELECT 1",
            )

    def test_sql_required(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="",
            )

    def test_limit_defaults_to_1000(self):
        req = SqlExecuteRequest(connection_id=1, database="mydb", sql="SELECT 1")
        assert req.limit == 1000

    def test_limit_must_be_positive(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="SELECT 1",
                limit=0,
            )

    def test_limit_capped_at_max(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="SELECT 1",
                limit=100_001,
            )