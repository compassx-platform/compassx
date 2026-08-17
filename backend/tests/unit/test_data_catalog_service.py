"""
Unit tests for app.services.data_catalog_service

Coverage
--------
- Password encryption / decryption (Fernet round-trip)
- Connection CRUD (create, read, update, delete)
- test_connection_raw (mocked psycopg2)
- list_databases / list_schemas / list_tables (mocked psycopg2)
- execute_sql (mocked psycopg2)
- Error handling (connection not found, decryption failure)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session

from app.services import data_catalog_service as svc
from app.schemas.data_catalog import ConnectionCreate, ConnectionUpdate
from app.models.data_catalog import CatalogConnection


# ═══════════════════════════════════════════════════════════════════════════════
# Encryption helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestEncryption:

    def test_encrypt_returns_non_empty_string(self):
        cipher = svc.encrypt_password("my_secret_password")
        assert isinstance(cipher, str)
        assert len(cipher) > 0

    def test_encrypt_is_not_plaintext(self):
        cipher = svc.encrypt_password("my_secret_password")
        assert "my_secret_password" not in cipher

    def test_decrypt_round_trip(self):
        plain = "super_secret_123!"
        cipher = svc.encrypt_password(plain)
        recovered = svc.decrypt_password(cipher)
        assert recovered == plain

    def test_different_passwords_produce_different_ciphers(self):
        c1 = svc.encrypt_password("password1")
        c2 = svc.encrypt_password("password2")
        assert c1 != c2

    def test_same_password_produces_different_ciphers_each_time(self):
        """Fernet uses random IVs — same plaintext → different ciphertext."""
        c1 = svc.encrypt_password("same_password")
        c2 = svc.encrypt_password("same_password")
        assert c1 != c2  # different nonces

    def test_decrypt_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Cannot decrypt"):
            svc.decrypt_password("not-a-valid-fernet-token")


# ═══════════════════════════════════════════════════════════════════════════════
# Connection CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionCRUD:

    def test_create_connection_returns_integer_id(self, db_session: Session):
        conn = svc.create_connection(
            db_session,
            ConnectionCreate(
                name="My DB",
                host="db.example.com",
                port=5432,
                username="admin",
                password="pass123",
                default_database="mydb",
            ),
        )
        assert isinstance(conn.id, int)
        assert conn.id > 0

    def test_create_connection_stores_encrypted_password(self, db_session: Session):
        conn = svc.create_connection(
            db_session,
            ConnectionCreate(
                name="Encrypted DB",
                host="localhost",
                port=5432,
                username="user",
                password="plaintext_pass",
                default_database="db",
            ),
        )
        # Password must NOT be stored in plaintext
        assert conn.password_enc != "plaintext_pass"
        # But must be decryptable
        assert svc.decrypt_password(conn.password_enc) == "plaintext_pass"

    def test_create_connection_stores_correct_metadata(self, db_session: Session):
        conn = svc.create_connection(
            db_session,
            ConnectionCreate(
                name="Metadata DB",
                host="192.168.1.100",
                port=5433,
                username="dbuser",
                password="pass",
                default_database="analytics",
            ),
        )
        assert conn.name == "Metadata DB"
        assert conn.host == "192.168.1.100"
        assert conn.port == 5433
        assert conn.username == "dbuser"
        assert conn.default_database == "analytics"

    def test_get_connection_by_integer_id(self, db_session: Session, sample_catalog_connection):
        result = svc.get_connection(db_session, sample_catalog_connection.id)
        assert result is not None
        assert result.id == sample_catalog_connection.id

    def test_get_connection_returns_none_if_not_found(self, db_session: Session):
        result = svc.get_connection(db_session, 999999)
        assert result is None

    def test_list_connections_returns_all(self, db_session: Session, sample_catalog_connection):
        connections = svc.list_connections(db_session)
        assert len(connections) >= 1
        ids = [c.id for c in connections]
        assert sample_catalog_connection.id in ids

    def test_update_connection_name(self, db_session: Session, sample_catalog_connection):
        updated = svc.update_connection(
            db_session,
            sample_catalog_connection.id,
            ConnectionUpdate(name="Updated Name"),
        )
        assert updated is not None
        assert updated.name == "Updated Name"

    def test_update_connection_host(self, db_session: Session, sample_catalog_connection):
        updated = svc.update_connection(
            db_session,
            sample_catalog_connection.id,
            ConnectionUpdate(host="new-host.example.com"),
        )
        assert updated.host == "new-host.example.com"

    def test_update_connection_password_re_encrypts(
        self, db_session: Session, sample_catalog_connection
    ):
        old_cipher = sample_catalog_connection.password_enc
        updated = svc.update_connection(
            db_session,
            sample_catalog_connection.id,
            ConnectionUpdate(password="new_password_456"),
        )
        assert updated.password_enc != old_cipher
        assert svc.decrypt_password(updated.password_enc) == "new_password_456"

    def test_update_connection_returns_none_if_not_found(self, db_session: Session):
        result = svc.update_connection(
            db_session, 999999, ConnectionUpdate(name="Ghost")
        )
        assert result is None

    def test_delete_connection_returns_true(self, db_session: Session):
        conn = svc.create_connection(
            db_session,
            ConnectionCreate(
                name="To Delete",
                host="localhost",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            ),
        )
        result = svc.delete_connection(db_session, conn.id)
        assert result is True

    def test_delete_connection_removes_from_db(self, db_session: Session):
        conn = svc.create_connection(
            db_session,
            ConnectionCreate(
                name="To Delete 2",
                host="localhost",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            ),
        )
        conn_id = conn.id
        svc.delete_connection(db_session, conn_id)
        assert svc.get_connection(db_session, conn_id) is None

    def test_delete_connection_returns_false_if_not_found(self, db_session: Session):
        result = svc.delete_connection(db_session, 999999)
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Connection test (mocked psycopg2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionTest:

    @patch("app.services.data_catalog_service.psycopg2.connect")
    def test_test_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 15.0",)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = svc.test_connection_raw(
            host="localhost", port=5432,
            username="user", password="pass",
            database="testdb",
        )

        assert result["success"] is True
        assert result["server_version"] == "PostgreSQL 15.0"
        mock_conn.close.assert_called_once()

    @patch("app.services.data_catalog_service.psycopg2.connect")
    def test_test_connection_failure(self, mock_connect):
        import psycopg2
        mock_connect.side_effect = psycopg2.OperationalError("Connection refused")

        result = svc.test_connection_raw(
            host="bad-host", port=5432,
            username="user", password="pass",
            database="testdb",
        )

        assert result["success"] is False
        assert "Connection refused" in result["message"]

    @patch("app.services.data_catalog_service.psycopg2.connect")
    def test_test_connection_unexpected_error(self, mock_connect):
        mock_connect.side_effect = RuntimeError("Unexpected error")

        result = svc.test_connection_raw(
            host="localhost", port=5432,
            username="user", password="pass",
            database="testdb",
        )

        assert result["success"] is False
        assert "Unexpected error" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# Catalog browsing (mocked psycopg2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCatalogBrowsing:

    def _mock_conn_with_rows(self, rows: list[dict]) -> MagicMock:
        """Build a mock psycopg2 connection that returns the given rows."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_databases_returns_list(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_conn = self._mock_conn_with_rows([
            {"name": "postgres", "owner": "postgres"},
            {"name": "analytics", "owner": "admin"},
        ])
        mock_conn_from_record.return_value = mock_conn

        result = svc.list_databases(db_session, sample_catalog_connection.id)

        assert len(result) == 2
        assert result[0]["name"] == "postgres"

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_databases_raises_if_connection_not_found(
        self, mock_conn_from_record, db_session: Session
    ):
        with pytest.raises(ValueError, match="not found"):
            svc.list_databases(db_session, 999999)

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_schemas_returns_list(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_conn = self._mock_conn_with_rows([
            {"name": "public", "owner": "postgres"},
            {"name": "analytics", "owner": "admin"},
        ])
        mock_conn_from_record.return_value = mock_conn

        result = svc.list_schemas(db_session, sample_catalog_connection.id, "testdb")

        assert len(result) == 2
        assert result[0]["name"] == "public"

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_tables_returns_list(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_conn = self._mock_conn_with_rows([
            {"name": "users", "schema_name": "public", "table_type": "BASE TABLE", "row_estimate": 1000},
            {"name": "orders", "schema_name": "public", "table_type": "BASE TABLE", "row_estimate": 500},
        ])
        mock_conn_from_record.return_value = mock_conn

        result = svc.list_tables(db_session, sample_catalog_connection.id, "testdb", "public")

        assert len(result) == 2
        assert result[0]["name"] == "users"

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_list_databases_closes_connection(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_conn = self._mock_conn_with_rows([])
        mock_conn_from_record.return_value = mock_conn

        svc.list_databases(db_session, sample_catalog_connection.id)

        mock_conn.close.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# SQL execution (mocked psycopg2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecuteSQL:

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_returns_columns_and_rows(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",), ("value",)]
        mock_cursor.fetchall.return_value = [(1, "Alice", 100), (2, "Bob", 200)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        result = svc.execute_sql(
            db_session, sample_catalog_connection.id, "testdb",
            "SELECT id, name, value FROM users", limit=1000,
        )

        assert result.columns == ["id", "name", "value"]
        assert result.row_count == 2
        assert result.error is None

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_truncates_at_limit(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        # Return limit+1 rows to trigger truncation
        mock_cursor.fetchall.return_value = [(i,) for i in range(6)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        result = svc.execute_sql(
            db_session, sample_catalog_connection.id, "testdb",
            "SELECT id FROM t", limit=5,
        )

        assert result.row_count == 5
        assert result.truncated is True

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_returns_error_on_psycopg2_error(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        import psycopg2
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError("syntax error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        result = svc.execute_sql(
            db_session, sample_catalog_connection.id, "testdb",
            "SELEKT * FROM bad_sql", limit=100,
        )

        assert result.error is not None
        assert "syntax error" in result.error

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_raises_if_connection_not_found(
        self, mock_conn_from_record, db_session: Session
    ):
        with pytest.raises(ValueError, match="not found"):
            svc.execute_sql(db_session, 999999, "testdb", "SELECT 1", limit=100)

    @patch("app.services.data_catalog_service._conn_from_record")
    def test_execute_sql_rolls_back_after_read(
        self, mock_conn_from_record, db_session: Session, sample_catalog_connection
    ):
        """Ensure rollback is called to enforce read-only behaviour."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("val",)]
        mock_cursor.fetchall.return_value = [(42,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_from_record.return_value = mock_conn

        svc.execute_sql(
            db_session, sample_catalog_connection.id, "testdb", "SELECT 42", limit=100
        )

        mock_conn.rollback.assert_called_once()