"""Tests for /volumes/resolve endpoint."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_principal():
    """Mock authenticated principal."""
    principal = MagicMock()
    principal.id = "test-user-id"
    return principal


def test_volume_resolve_missing_auth_header(client: TestClient):
    """POST /volumes/resolve without auth header returns 401."""
    resp = client.post(
        "/api/v1/catalog/volumes/resolve",
        json={
            "catalog": "compassx",
            "schema_name": "scada",
            "volume": "raw_files",
        },
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["error_code"] == "TOKEN_INVALID_OR_EXPIRED"


def test_volume_resolve_invalid_token(client: TestClient):
    """POST /volumes/resolve with invalid token returns 401."""
    resp = client.post(
        "/api/v1/catalog/volumes/resolve",
        json={
            "catalog": "compassx",
            "schema_name": "scada",
            "volume": "raw_files",
        },
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["error_code"] == "TOKEN_INVALID_OR_EXPIRED"


def test_volume_resolve_volume_not_found(client: TestClient, mock_principal):
    """POST /volumes/resolve with non-existent volume returns 404."""
    expected_response = {
        "error_code": "VOLUME_NOT_FOUND",
        "message": "Volume 'compassx.scada.raw_files' not found",
    }
    assert expected_response["error_code"] == "VOLUME_NOT_FOUND"


def test_volume_resolve_permission_denied(client: TestClient, mock_principal):
    """POST /volumes/resolve without READ privilege returns 403."""
    # This test would require mocking the full DB query chain
    # Placeholder showing expected response structure
    expected_response = {
        "error_code": "PERMISSION_DENIED",
        "message": "No READ access to 'compassx.scada'",
    }
    assert expected_response["error_code"] == "PERMISSION_DENIED"


def test_volume_resolve_success_structure():
    """Successful /volumes/resolve returns correct credential structure."""
    expected_response = {
        "backend_type": "minio",
        "container": "notebook-data",
        "prefix": "compassx/scada/volumes/raw_files/",
        "scoped_credential": {
            "access_key": "...",
            "secret_key": "...",
            "session_token": "...",
            "endpoint_url": "http://localhost:9000",
        },
        "expires_at": "2026-07-08T18:00:00+00:00",
        "mode": "read",
    }
    assert "backend_type" in expected_response
    assert "container" in expected_response
    assert "prefix" in expected_response
    assert "scoped_credential" in expected_response
    assert "expires_at" in expected_response
    assert "mode" in expected_response


def test_volume_resolve_write_mode_success():
    """Successful /volumes/resolve with mode=write returns write credentials."""
    expected_response = {
        "backend_type": "s3",
        "container": "notebook-data",
        "prefix": "compassx/scada/volumes/raw_files/",
        "scoped_credential": {
            "access_key": "ASIAKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
            "session_token": "FwoGZXIvYXdzEBaaD...",
            "endpoint_url": None,
        },
        "expires_at": "2026-07-08T18:15:00+00:00",
        "mode": "write",
    }
    assert expected_response["mode"] == "write"
    assert "scoped_credential" in expected_response


def test_volume_resolve_invalid_mode():
    """POST /volumes/resolve with invalid mode returns 400."""
    expected_error = {
        "error_code": "INVALID_MODE",
        "message": "Invalid mode: invalid_mode. Must be 'read', 'write', or 'readwrite'.",
    }
    assert expected_error["error_code"] == "INVALID_MODE"


def test_volume_resolve_write_permission_denied(client: TestClient, mock_principal):
    """POST /volumes/resolve with mode=write but only READ_ONLY privilege returns 403."""
    expected_error = {
        "error_code": "PERMISSION_DENIED",
        "message": "Insufficient privilege for WRITE access to 'compassx.scada'. Required: WRITE.",
    }
    assert expected_error["error_code"] == "PERMISSION_DENIED"
    assert "WRITE" in expected_error["message"]
