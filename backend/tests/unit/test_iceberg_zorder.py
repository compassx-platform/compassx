import json
import pytest
from unittest.mock import AsyncMock

from app.catalog.iceberg_manager import IcebergManager


@pytest.mark.asyncio
async def test_iceberg_create_table_with_zorder():
    storage = AsyncMock()
    written_files = {}

    async def mock_write_bytes(path, data, content_type=None):
        written_files[path] = data

    storage.write_bytes = mock_write_bytes
    mgr = IcebergManager(storage)

    columns = [
        {"name": "turbine_id", "data_type": "string", "nullable": False},
        {"name": "power_kw", "data_type": "float64", "nullable": True},
        {"name": "ts", "data_type": "timestamp", "nullable": True},
    ]

    meta_rel = await mgr.create_table(
        table_path="catalogs/prod/tables/telemetry",
        table_name="telemetry",
        columns=columns,
        z_order_by=["turbine_id", "ts"],
    )

    assert meta_rel == "catalogs/prod/tables/telemetry/metadata/v1.metadata.json"
    assert meta_rel in written_files

    meta_json = json.loads(written_files[meta_rel].decode())
    assert meta_json["default-sort-order-id"] == 1
    assert len(meta_json["sort-orders"]) == 1
    sort_order = meta_json["sort-orders"][0]
    assert sort_order["order-id"] == 1
    assert len(sort_order["fields"]) == 2

    # turbine_id is field id 1, ts is field id 3
    assert sort_order["fields"][0]["source-id"] == 1
    assert sort_order["fields"][0]["direction"] == "asc"
    assert sort_order["fields"][1]["source-id"] == 3
    assert sort_order["fields"][1]["direction"] == "asc"
    assert meta_json["properties"]["compassx.z-order-by"] == "turbine_id,ts"


@pytest.mark.asyncio
async def test_iceberg_commit_compaction():
    storage = AsyncMock()
    v1_meta = {
        "format-version": 2,
        "table-uuid": "test-uuid",
        "current-schema-id": 0,
        "schemas": [
            {
                "schema-id": 0,
                "type": "struct",
                "fields": [
                    {"id": 1, "name": "region", "type": "string", "required": False},
                    {"id": 2, "name": "val", "type": "int", "required": False},
                ],
            }
        ],
        "default-sort-order-id": 0,
        "sort-orders": [{"order-id": 0, "fields": []}],
        "current-snapshot-id": 100,
        "snapshots": [
            {"snapshot-id": 100, "timestamp-ms": 1000, "summary": {"operation": "append"}}
        ],
        "snapshot-log": [],
        "metadata-log": [],
    }

    storage.get_metadata_location = AsyncMock(return_value="catalogs/prod/tables/metrics/metadata/v1.metadata.json")
    storage.exists = AsyncMock(return_value=True)
    storage.read_bytes = AsyncMock(return_value=json.dumps(v1_meta).encode())
    written_files = {}

    async def mock_write_bytes(path, data, content_type=None):
        written_files[path] = data

    storage.write_bytes = mock_write_bytes
    mgr = IcebergManager(storage)
    mgr.get_metadata_location = AsyncMock(return_value="catalogs/prod/tables/metrics/metadata/v1.metadata.json")

    v2_meta_path = await mgr.commit_compaction(
        table_path="catalogs/prod/tables/metrics",
        compacted_file_name="compacted_xyz.parquet",
        total_records=5000,
        deleted_files_count=5,
        z_order_by=["region", "val"],
    )

    assert v2_meta_path == "catalogs/prod/tables/metrics/metadata/v2.metadata.json"
    assert v2_meta_path in written_files
    meta_json = json.loads(written_files[v2_meta_path].decode())

    assert meta_json["default-sort-order-id"] == 1
    assert meta_json["sort-orders"][0]["fields"][0]["source-id"] == 1
    assert meta_json["sort-orders"][0]["fields"][1]["source-id"] == 2
    assert meta_json["snapshots"][-1]["summary"]["operation"] == "replace"
    assert meta_json["snapshots"][-1]["summary"]["added-records"] == "5000"
    assert meta_json["snapshots"][-1]["summary"]["deleted-data-files"] == "5"
    assert meta_json["snapshots"][-1]["summary"]["z_ordered"] == "true"
