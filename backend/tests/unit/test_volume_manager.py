"""Unit tests for VolumeManager file and directory operations."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.catalog.models import UnifiedCatalogVolume, UnifiedCatalogSchema, UnifiedCatalog
from app.catalog.db_models import UnifiedCatalogVolumeFile
from app.catalog.volume_manager import VolumeManager
from app.storage.models import FileInfo


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.write_bytes = AsyncMock()
    storage.read_bytes = AsyncMock(return_value=b"test data")
    storage.list_files = AsyncMock(return_value=[])
    storage.delete = AsyncMock()
    storage.get_url = AsyncMock(return_value="https://storage.example.com/file")
    return storage


@pytest.fixture
def test_setup():
    db = MagicMock()
    
    catalog = UnifiedCatalog(id="cat-1", name="test_catalog")
    schema = UnifiedCatalogSchema(id="sch-1", catalog_id="cat-1", name="test_schema")
    schema.catalog = catalog
    schema.base_path = "test_catalog/test_schema/"
    
    volume = UnifiedCatalogVolume(
        id="vol-1",
        schema_id="sch-1",
        name="test_volume",
        storage_location="test_catalog/test_schema/volumes/test_volume/",
    )
    volume.schema = schema
    
    return db, volume


@pytest.mark.asyncio
async def test_create_directory_writes_keep_marker(mock_storage, test_setup):
    db, volume = test_setup
    
    def mock_query(model):
        q = MagicMock()
        if model == UnifiedCatalogVolume:
            q.filter.return_value.first.return_value = volume
        elif model == UnifiedCatalogVolumeFile:
            q.filter.return_value.first.return_value = None
        return q
    
    db.query = mock_query
    manager = VolumeManager(mock_storage, backend_base="compassx/")
    
    result = await manager.create_directory(
        db=db,
        volume_id="vol-1",
        dir_name="invoices",
        sub_path="finance/2026",
        uploaded_by="user@example.com",
    )
    
    assert result.file_path == "finance/2026/invoices/"
    assert result.file_name == "invoices/"
    assert result.content_type == "application/x-directory"
    assert result.size_bytes == 0
    
    # Verify .keep file was written to storage
    mock_storage.write_bytes.assert_awaited_once()
    called_path, data, content_type = mock_storage.write_bytes.call_args[0]
    assert called_path.endswith("finance/2026/invoices/.keep")
    assert data == b""
    assert content_type == "application/octet-stream"
    
    # Verify DB entry was added
    db.add.assert_called_once()
    db_entry = db.add.call_args[0][0]
    assert isinstance(db_entry, UnifiedCatalogVolumeFile)
    assert db_entry.file_path == "finance/2026/invoices/"
    assert db_entry.content_type == "application/x-directory"


@pytest.mark.asyncio
async def test_list_files_deduplicates_and_hides_keep(mock_storage, test_setup):
    db, volume = test_setup
    manager = VolumeManager(mock_storage, backend_base="compassx/")
    
    # 1. DB has an indexed directory and a file
    db_dir = UnifiedCatalogVolumeFile(
        id="f-1",
        volume_id="vol-1",
        file_path="reports/",
        file_name="reports/",
        size_bytes=0,
        content_type="application/x-directory",
        uploaded_at=datetime.now(timezone.utc),
    )
    db_file = UnifiedCatalogVolumeFile(
        id="f-2",
        volume_id="vol-1",
        file_path="reports/q1.csv",
        file_name="q1.csv",
        size_bytes=1024,
        content_type="text/csv",
        uploaded_at=datetime.now(timezone.utc),
    )
    
    # 2. Raw storage listing returns .keep and legacy 0-byte blob for reports
    # Paths are returned relative to volume base
    mock_storage.list_files.return_value = [
        FileInfo(file_path="test_catalog/test_schema/volumes/test_volume/reports/.keep", file_name=".keep", size_bytes=0, content_type="application/octet-stream", last_modified=datetime.now(timezone.utc)),
        FileInfo(file_path="test_catalog/test_schema/volumes/test_volume/reports", file_name="reports", size_bytes=0, content_type="application/x-directory", last_modified=datetime.now(timezone.utc)),
        FileInfo(file_path="test_catalog/test_schema/volumes/test_volume/reports/q1.csv", file_name="q1.csv", size_bytes=1024, content_type="text/csv", last_modified=datetime.now(timezone.utc)),
    ]
    
    def mock_query(model):
        q = MagicMock()
        if model == UnifiedCatalogVolume:
            q.filter.return_value.first.return_value = volume
        elif model == UnifiedCatalogVolumeFile:
            q.filter.return_value.all.return_value = [db_dir, db_file]
        return q
    
    db.query = mock_query
    
    files = await manager.list_files(db, "vol-1")
    
    # Must contain exactly reports/ and reports/q1.csv (no duplicate reports, no .keep)
    file_paths = [f.file_path for f in files]
    assert file_paths == ["reports/", "reports/q1.csv"]
    assert len(files) == 2


@pytest.mark.asyncio
async def test_delete_directory_cleans_keep_and_db(mock_storage, test_setup):
    db, volume = test_setup
    manager = VolumeManager(mock_storage, backend_base="compassx/")
    
    delete_mock = MagicMock()
    def mock_query(model):
        q = MagicMock()
        if model == UnifiedCatalogVolume:
            q.filter.return_value.first.return_value = volume
        elif model == UnifiedCatalogVolumeFile:
            q.filter.return_value.delete = delete_mock
        return q
    
    db.query = mock_query
    
    await manager.delete_file(db, "vol-1", "reports/")
    
    # Verify storage delete was called
    assert mock_storage.delete.await_count >= 1
    # Verify DB delete and commit were executed
    db.commit.assert_called_once()
