"""Tests for CXFileSystem (cx:// protocol)."""
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from services.fsspec_cx.cx_protocol import CXFileSystem, _fsspec_mode_to_cx_mode
from services.fsspec_cx.credential_cache import CredentialCache
from services.fsspec_cx.exceptions import map_resolve_error


class TestCXFileSystemPathParsing:
    """Test cx:// path parsing."""

    def test_parse_valid_path_with_file(self):
        """Parse valid cx://catalog.schema.volume/path/to/file.csv."""
        fs = CXFileSystem()
        catalog, schema, volume, file_path = fs._parse_path(
            "compassx.scada.raw_files/data/2026/file.csv"
        )
        assert catalog == "compassx"
        assert schema == "scada"
        assert volume == "raw_files"
        assert file_path == "data/2026/file.csv"

    def test_parse_valid_path_without_file(self):
        """Parse valid cx://catalog.schema.volume (directory-like)."""
        fs = CXFileSystem()
        catalog, schema, volume, file_path = fs._parse_path(
            "compassx.scada.raw_files"
        )
        assert catalog == "compassx"
        assert schema == "scada"
        assert volume == "raw_files"
        assert file_path == ""

    def test_parse_invalid_path_too_few_dots(self):
        """Parse invalid cx://catalog.schema (missing volume)."""
        fs = CXFileSystem()
        with pytest.raises(ValueError, match="Invalid cx:// path format"):
            fs._parse_path("compassx.scada")

    def test_parse_invalid_path_too_many_dots(self):
        """Parse invalid cx://catalog.schema.volume.extra."""
        fs = CXFileSystem()
        with pytest.raises(ValueError, match="Invalid cx:// path format"):
            fs._parse_path("compassx.scada.volume.extra/file.csv")

    def test_parse_path_with_leading_slash(self):
        """Parse path with leading slash stripped."""
        fs = CXFileSystem()
        catalog, schema, volume, file_path = fs._parse_path(
            "/compassx.scada.raw_files/file.csv"
        )
        assert catalog == "compassx"
        assert schema == "scada"
        assert volume == "raw_files"
        assert file_path == "file.csv"


class TestCredentialCache:
    """Test credential caching logic."""

    def test_cache_miss_on_first_access(self):
        """First access to volume should mint new credential."""
        cache = CredentialCache()
        cache.set_session_token("test-token", "http://api.example.com")

        mock_credential = {
            "backend_type": "minio",
            "container": "bucket",
            "prefix": "prefix/",
            "scoped_credential": {"access_key": "key"},
            "expires_at": "2026-07-08T18:00:00+00:00",
        }

        with patch("services.fsspec_cx.credential_cache.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_credential
            mock_post.return_value = mock_resp

            result = cache.get_or_mint("catalog", "schema", "volume")

            assert result == mock_credential
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["catalog"] == "catalog"

    def test_cache_hit_on_second_access(self):
        """Second access to same volume should reuse cached credential."""
        cache = CredentialCache()
        cache.set_session_token("test-token", "http://api.example.com")

        mock_credential = {
            "backend_type": "minio",
            "container": "bucket",
            "prefix": "prefix/",
            "scoped_credential": {"access_key": "key"},
            "expires_at": "2099-12-31T00:00:00+00:00",  # Far in future
        }

        with patch("services.fsspec_cx.credential_cache.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_credential
            mock_post.return_value = mock_resp

            # First call
            result1 = cache.get_or_mint("catalog", "schema", "volume")
            assert result1 == mock_credential

            # Second call should use cache
            result2 = cache.get_or_mint("catalog", "schema", "volume")
            assert result2 == mock_credential

            # httpx.post should only be called once
            assert mock_post.call_count == 1

    def test_error_handling_volume_not_found(self):
        """Credential resolve 404 should raise FileNotFoundError."""
        cache = CredentialCache()
        cache.set_session_token("test-token", "http://api.example.com")

        with patch("services.fsspec_cx.credential_cache.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.json.return_value = {
                "error_code": "VOLUME_NOT_FOUND",
                "message": "Volume not found",
            }
            mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
            mock_post.return_value = mock_resp

            mock_post.return_value.raise_for_status.side_effect = \
                __import__("httpx").HTTPStatusError("404", request=MagicMock(), response=mock_resp)

            with pytest.raises(FileNotFoundError):
                cache.get_or_mint("catalog", "schema", "volume")


class TestErrorMapping:
    """Test error code to exception mapping."""

    def test_volume_not_found_maps_to_file_not_found_error(self):
        """VOLUME_NOT_FOUND error code raises FileNotFoundError."""
        exc = map_resolve_error("VOLUME_NOT_FOUND", "Volume not found")
        assert isinstance(exc, FileNotFoundError)
        assert "VOLUME_NOT_FOUND" in str(exc)

    def test_permission_denied_maps_to_permission_error(self):
        """PERMISSION_DENIED error code raises PermissionError."""
        exc = map_resolve_error("PERMISSION_DENIED", "No READ access")
        assert isinstance(exc, PermissionError)
        assert "PERMISSION_DENIED" in str(exc)

    def test_token_error_maps_to_permission_error(self):
        """TOKEN_INVALID_OR_EXPIRED error code raises PermissionError."""
        exc = map_resolve_error("TOKEN_INVALID_OR_EXPIRED", "Token expired")
        assert isinstance(exc, PermissionError)
        assert "TOKEN_INVALID_OR_EXPIRED" in str(exc)

    def test_mint_failed_maps_to_os_error(self):
        """CREDENTIAL_MINT_FAILED error code raises OSError."""
        exc = map_resolve_error("CREDENTIAL_MINT_FAILED", "STS unavailable")
        assert isinstance(exc, OSError)
        assert "CREDENTIAL_MINT_FAILED" in str(exc)

    def test_unknown_error_code_maps_to_os_error(self):
        """Unknown error code defaults to OSError."""
        exc = map_resolve_error("UNKNOWN_ERROR", "Something went wrong")
        assert isinstance(exc, OSError)


class TestFsspecModeDetection:
    """Test fsspec mode → cx mode conversion."""

    def test_read_mode_rb(self):
        """fsspec mode 'rb' maps to cx mode 'read'."""
        assert _fsspec_mode_to_cx_mode("rb") == "read"

    def test_read_mode_r(self):
        """fsspec mode 'r' maps to cx mode 'read'."""
        assert _fsspec_mode_to_cx_mode("r") == "read"

    def test_write_mode_wb(self):
        """fsspec mode 'wb' maps to cx mode 'write'."""
        assert _fsspec_mode_to_cx_mode("wb") == "write"

    def test_write_mode_w(self):
        """fsspec mode 'w' maps to cx mode 'write'."""
        assert _fsspec_mode_to_cx_mode("w") == "write"

    def test_append_mode_ab(self):
        """fsspec mode 'ab' maps to cx mode 'write'."""
        assert _fsspec_mode_to_cx_mode("ab") == "write"

    def test_append_mode_a(self):
        """fsspec mode 'a' maps to cx mode 'write'."""
        assert _fsspec_mode_to_cx_mode("a") == "write"

    def test_readwrite_mode_r_plus(self):
        """fsspec mode 'r+' maps to cx mode 'readwrite'."""
        assert _fsspec_mode_to_cx_mode("r+") == "readwrite"

    def test_readwrite_mode_r_plus_b(self):
        """fsspec mode 'r+b' maps to cx mode 'readwrite'."""
        assert _fsspec_mode_to_cx_mode("r+b") == "readwrite"

    def test_readwrite_mode_w_plus(self):
        """fsspec mode 'w+' maps to cx mode 'readwrite'."""
        assert _fsspec_mode_to_cx_mode("w+") == "readwrite"

    def test_readwrite_mode_w_plus_b(self):
        """fsspec mode 'w+b' maps to cx mode 'readwrite'."""
        assert _fsspec_mode_to_cx_mode("w+b") == "readwrite"


class TestCredentialCacheModeIsolation:
    """Test mode-specific credential caching."""

    def test_cache_key_includes_mode(self):
        """Cache key should include mode for isolation."""
        cache = CredentialCache()
        key_read = cache._cache_key("catalog", "schema", "volume", "read")
        key_write = cache._cache_key("catalog", "schema", "volume", "write")

        assert key_read != key_write
        assert key_read == ("catalog", "schema", "volume", "read")
        assert key_write == ("catalog", "schema", "volume", "write")

    def test_cache_hit_read_no_hit_write(self):
        """Read mode cache hit should not prevent write mode cache miss."""
        cache = CredentialCache()
        cache.set_session_token("test-token", "http://api.example.com")

        mock_read_cred = {
            "backend_type": "s3",
            "container": "bucket",
            "prefix": "prefix/",
            "scoped_credential": {"access_key": "read-key"},
            "expires_at": "2099-12-31T00:00:00+00:00",
            "mode": "read",
        }
        mock_write_cred = {
            "backend_type": "s3",
            "container": "bucket",
            "prefix": "prefix/",
            "scoped_credential": {"access_key": "write-key"},
            "expires_at": "2099-12-31T00:00:00+00:00",
            "mode": "write",
        }

        with patch("services.fsspec_cx.credential_cache.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.side_effect = [mock_read_cred, mock_write_cred]
            mock_post.return_value = mock_resp

            # First: get read credentials
            result_read = cache.get_or_mint("catalog", "schema", "volume", mode="read")
            assert result_read["scoped_credential"]["access_key"] == "read-key"

            # Second: get write credentials (should be cache miss, not reuse read)
            result_write = cache.get_or_mint("catalog", "schema", "volume", mode="write")
            assert result_write["scoped_credential"]["access_key"] == "write-key"

            # httpx.post should be called twice (once per mode)
            assert mock_post.call_count == 2

    def test_post_request_includes_mode(self):
        """POST to /volumes/resolve should include mode parameter."""
        cache = CredentialCache()
        cache.set_session_token("test-token", "http://api.example.com")

        mock_credential = {
            "backend_type": "s3",
            "container": "bucket",
            "prefix": "prefix/",
            "scoped_credential": {"access_key": "key"},
            "expires_at": "2026-07-08T18:00:00+00:00",
            "mode": "write",
        }

        with patch("services.fsspec_cx.credential_cache.httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_credential
            mock_post.return_value = mock_resp

            cache.get_or_mint("catalog", "schema", "volume", mode="write")

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["mode"] == "write"
            assert call_kwargs["json"]["schema_name"] == "schema"  # Verify field name fix
