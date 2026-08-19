import pytest
from unittest.mock import MagicMock, patch

from app.config import settings
from app.workspace.storage_resolver import (
    get_managed_storage_config,
    resolve_workspace_storage,
    ensure_default_storage_bucket,
)


def test_get_managed_storage_config_minio():
    with patch.object(settings, "STORAGE_BACKEND", "minio"), \
         patch.object(settings, "STORAGE_ENDPOINT", "http://minio:9000"), \
         patch.object(settings, "STORAGE_BUCKET", "compassx"), \
         patch.object(settings, "STORAGE_ACCESS_KEY", "minioadmin"), \
         patch.object(settings, "STORAGE_SECRET_KEY", "minioadmin"), \
         patch.object(settings, "STORAGE_PREFIX", ""):

        backend, config = get_managed_storage_config("engineering")
        assert backend == "minio"
        assert config["endpoint"] == "http://minio:9000"
        assert config["bucket"] == "compassx"
        assert config["access_key"] == "minioadmin"
        assert config["secret_key"] == "minioadmin"
        assert config["prefix"] == "workspaces/engineering/"


def test_resolve_workspace_storage_managed():
    workspace = MagicMock()
    workspace.slug = "default"
    workspace.storage_backend = "managed"
    workspace.storage_config = {}

    with patch.object(settings, "STORAGE_BACKEND", "minio"), \
         patch.object(settings, "STORAGE_BUCKET", "compassx"):
        backend, config = resolve_workspace_storage(workspace)
        assert backend == "minio"
        assert config["bucket"] == "compassx"
        assert config["prefix"] == "workspaces/default/"


def test_resolve_workspace_storage_custom():
    workspace = MagicMock()
    workspace.slug = "custom-ws"
    workspace.storage_backend = "s3"
    workspace.storage_config = {
        "bucket": "my-custom-bucket",
        "region": "us-west-2",
        "access_key": "custom-key",
        "secret_key": "custom-secret",
        "prefix": "custom-prefix/",
    }

    backend, config = resolve_workspace_storage(workspace)
    assert backend == "s3"
    assert config["bucket"] == "my-custom-bucket"
    assert config["prefix"] == "custom-prefix/"
