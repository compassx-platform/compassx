"""IcebergManager — writes Iceberg v2 metadata JSON to blob storage.

CompassX acts as the Iceberg catalog. No external Hive Metastore or REST catalog
is required. External pipelines write Parquet data; CompassX registers the metadata.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.storage.backend import BlobStorageBackend

logger = logging.getLogger(__name__)

# CompassX column type → Iceberg type mapping
COMPASSX_TO_ICEBERG: dict[str, str] = {
    "int32": "int",
    "int64": "long",
    "int16": "short",
    "float32": "float",
    "float64": "double",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
    "timestamp": "timestamp",
    "timestamptz": "timestamptz",
    "date": "date",
    "time": "time",
    "decimal": "decimal(38,10)",
    "uuid": "uuid",
    "binary": "binary",
    "json": "string",
    # pass-through for already-iceberg types
    "int": "int",
    "long": "long",
    "double": "double",
}


class IcebergManager:
    """Writes Iceberg schema markers and table metadata to blob storage."""

    def __init__(self, storage_backend: BlobStorageBackend) -> None:
        self.storage = storage_backend

    async def create_schema(self, schema_path: str) -> None:
        """
        Write a lightweight marker file to blob storage to establish the schema path.
        The schema itself is purely a catalog concept; this ensures the path exists.
        """
        marker = {
            "compassx_schema": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.storage.write_bytes(
            path=f"{schema_path.rstrip('/')}/_compassx_schema.json",
            data=json.dumps(marker, indent=2).encode(),
            content_type="application/json",
        )
        logger.info("Iceberg schema path created: %s", schema_path)

    async def create_table(
        self,
        table_path: str,
        table_name: str,
        columns: list[dict],
        properties: dict | None = None,
    ) -> str:
        """
        Write initial Iceberg v2 metadata JSON to blob storage.

        Returns the metadata_location path (relative to backend base_path).

        columns: list of dicts with keys: name, data_type, nullable (bool), description (str)
        """
        if properties is None:
            properties = {}

        schema_id = 0
        fields = []
        for idx, col in enumerate(columns):
            raw_type = col.get("data_type", "string")
            iceberg_type = COMPASSX_TO_ICEBERG.get(raw_type, raw_type)
            fields.append({
                "id": idx + 1,
                "name": col["name"],
                "required": not col.get("nullable", True),
                "type": iceberg_type,
                "doc": col.get("description", ""),
            })

        metadata = {
            "format-version": 2,
            "table-uuid": str(uuid.uuid4()),
            "location": table_path,
            "last-sequence-number": 0,
            "last-updated-ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "last-column-id": len(fields),
            "current-schema-id": schema_id,
            "schemas": [{"schema-id": schema_id, "type": "struct", "fields": fields}],
            "default-spec-id": 0,
            "partition-specs": [{"spec-id": 0, "fields": []}],
            "last-partition-id": 999,
            "default-sort-order-id": 0,
            "sort-orders": [{"order-id": 0, "fields": []}],
            "properties": {
                "created-by": "compassx",
                "write.format.default": "parquet",
                **properties,
            },
            "current-snapshot-id": -1,
            "snapshots": [],
            "snapshot-log": [],
            "metadata-log": [],
        }

        metadata_path = f"{table_path.rstrip('/')}/metadata/v1.metadata.json"
        await self.storage.write_bytes(
            path=metadata_path,
            data=json.dumps(metadata, indent=2).encode(),
            content_type="application/json",
        )
        # Write version-hint.text so DuckDB (and other engines) can find the
        # current metadata version without filesystem globbing.
        await self.storage.write_bytes(
            path=f"{table_path.rstrip('/')}/metadata/version-hint.text",
            data=b"1",
            content_type="text/plain",
        )
        # Write empty data directory marker
        await self.storage.write_bytes(
            path=f"{table_path.rstrip('/')}/data/_keep",
            data=b"",
            content_type="application/octet-stream",
        )
        logger.info("Iceberg table created at %s (%d columns)", table_path, len(fields))
        return metadata_path

    async def table_exists(self, table_path: str) -> bool:
        return await self.storage.exists(f"{table_path.rstrip('/')}/metadata/v1.metadata.json")

    async def get_metadata_location(self, table_path: str) -> str:
        """
        Resolve the latest metadata.json path for an existing Iceberg table.
        Checks for version-hint.text first, then falls back to highest-numbered file.
        """
        hint_path = f"{table_path.rstrip('/')}/metadata/version-hint.text"
        if await self.storage.exists(hint_path):
            hint = await self.storage.read_bytes(hint_path)
            version = hint.decode().strip()
            return f"{table_path.rstrip('/')}/metadata/v{version}.metadata.json"

        files = await self.storage.list_files(f"{table_path.rstrip('/')}/metadata/")
        metadata_files = [
            f for f in files
            if f.file_name.endswith(".metadata.json") and f.file_name.startswith("v")
        ]
        if not metadata_files:
            raise ValueError(f"No Iceberg metadata found at {table_path}")

        metadata_files.sort(
            key=lambda f: int(f.file_name.split(".")[0].lstrip("v")),
            reverse=True,
        )
        return metadata_files[0].file_path

    async def append_data_file(
        self,
        table_path: str,
        data_file_name: str,
        records_count: int,
        properties: dict | None = None,
    ) -> str:
        """
        Append a new data file commit to an existing Iceberg table metadata.
        Generates the next metadata version (v{N+1}.metadata.json), records snapshot,
        and updates version-hint.text.
        """
        latest_meta_rel = await self.get_metadata_location(table_path)
        raw_meta = await self.storage.read_bytes(latest_meta_rel)
        meta = json.loads(raw_meta.decode())

        # Determine current and next version numbers
        curr_ver_str = latest_meta_rel.split("/")[-1].split(".")[0].lstrip("v")
        try:
            curr_ver = int(curr_ver_str)
        except ValueError:
            curr_ver = 1
        next_ver = curr_ver + 1

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        snapshot_id = int(datetime.now(timezone.utc).timestamp() * 1000)

        data_file_rel = f"{table_path.rstrip('/')}/data/{data_file_name}"

        # Create new snapshot entry
        new_snapshot = {
            "snapshot-id": snapshot_id,
            "parent-snapshot-id": meta.get("current-snapshot-id", -1) if meta.get("current-snapshot-id", -1) != -1 else None,
            "timestamp-ms": now_ms,
            "summary": {
                "operation": "append",
                "added-data-files": "1",
                "added-records": str(records_count),
                "added-files-size": "0",
                **(properties or {}),
            },
            "manifest-list": data_file_rel,
            "schema-id": meta.get("current-schema-id", 0),
        }

        snapshots = meta.get("snapshots", [])
        snapshots.append(new_snapshot)
        meta["snapshots"] = snapshots
        meta["current-snapshot-id"] = snapshot_id
        meta["last-updated-ms"] = now_ms

        snapshot_log = meta.get("snapshot-log", [])
        snapshot_log.append({"timestamp-ms": now_ms, "snapshot-id": snapshot_id})
        meta["snapshot-log"] = snapshot_log

        metadata_log = meta.get("metadata-log", [])
        metadata_log.append({"timestamp-ms": now_ms, "metadata-file": latest_meta_rel})
        meta["metadata-log"] = metadata_log

        next_meta_path = f"{table_path.rstrip('/')}/metadata/v{next_ver}.metadata.json"
        await self.storage.write_bytes(
            path=next_meta_path,
            data=json.dumps(meta, indent=2).encode(),
            content_type="application/json",
        )
        await self.storage.write_bytes(
            path=f"{table_path.rstrip('/')}/metadata/version-hint.text",
            data=str(next_ver).encode(),
            content_type="text/plain",
        )
        logger.info("Iceberg table updated at %s (v%d snapshot %d)", table_path, next_ver, snapshot_id)
        return next_meta_path

