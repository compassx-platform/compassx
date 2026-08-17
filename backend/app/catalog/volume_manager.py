"""VolumeManager — file operations (upload / list / download / delete) for catalog volumes.

Volumes are managed blob-storage paths under a schema. They are not queryable as tables —
they are raw file storage for CSVs, JSON exports, reports, and documents.
"""
from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.catalog.models import UnifiedCatalogSchema, UnifiedCatalogVolume, UnifiedCatalog
from app.storage.backend import BlobStorageBackend
from app.storage.models import FileInfo

logger = logging.getLogger(__name__)


class VolumeManager:
    """
    File-level operations on volumes backed by a BlobStorageBackend.

    volume.storage_location is an *absolute* path from the container root
    (same as how IcebergManager stores paths).  The BlobStorageBackend
    prepends its own base_path to every call, so we must strip backend_base
    before passing paths to the backend.
    """

    def __init__(self, storage_backend: BlobStorageBackend, backend_base: str) -> None:
        self.storage = storage_backend
        # backend_base must end with "/" (e.g. "compassx/")
        self.backend_base = backend_base.rstrip("/") + "/" if backend_base else ""

    def _rel(self, absolute_path: str) -> str:
        """Convert an absolute container path to a backend-relative path."""
        path = absolute_path.strip("/")
        if path.startswith("compassx/"):
            path = path[len("compassx/"):]
        base = self.backend_base.strip("/")
        if base and path.startswith(base + "/"):
            path = path[len(base) + 1:]
        elif base and path == base:
            path = ""
        return path

    def _get_base_loc(self, volume: UnifiedCatalogVolume) -> str:
        if volume.storage_location:
            return volume.storage_location
        schema = volume.schema
        catalog = schema.catalog
        base = schema.base_path or f"{catalog.name}/{schema.name}/"
        return f"{base.rstrip('/')}/volumes/{volume.name}/"

    async def upload_file(
        self,
        db: Session,
        volume_id: str,
        file_name: str,
        data: bytes,
        sub_path: str = "",
        uploaded_by: str = "unknown",
    ) -> FileInfo:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")

        file_relative = f"{sub_path.strip('/')}/{file_name}".strip("/")
        base_loc = self._get_base_loc(volume)
        abs_path = f"{base_loc.rstrip('/')}/{file_relative}".strip("/")
        backend_rel = self._rel(abs_path)
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        await self.storage.write_bytes(backend_rel, data, content_type)

        # Index in volume_files table
        from app.catalog.db_models import UnifiedCatalogVolumeFile
        existing = (
            db.query(UnifiedCatalogVolumeFile)
            .filter(
                UnifiedCatalogVolumeFile.volume_id == volume_id,
                UnifiedCatalogVolumeFile.file_path == file_relative,
            )
            .first()
        )
        if existing:
            existing.size_bytes = len(data)
            existing.content_type = content_type
            existing.uploaded_by = uploaded_by
            existing.uploaded_at = datetime.now(timezone.utc)
        else:
            entry = UnifiedCatalogVolumeFile(
                volume_id=volume_id,
                file_path=file_relative,
                file_name=file_name,
                size_bytes=len(data),
                content_type=content_type,
                uploaded_by=uploaded_by,
            )
            db.add(entry)
        db.commit()

        logger.info("Uploaded %s to volume %s (%d bytes)", file_relative, volume_id, len(data))
        return FileInfo(
            file_path=file_relative,
            file_name=file_name,
            size_bytes=len(data),
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
        )

    async def create_directory(
        self,
        db: Session,
        volume_id: str,
        dir_name: str,
        sub_path: str = "",
        uploaded_by: str = "unknown",
    ) -> FileInfo:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")

        sub = sub_path.strip('/')
        dir_relative = f"{sub}/{dir_name}/" if sub else f"{dir_name}/"
        base_loc = self._get_base_loc(volume)
        abs_path = f"{base_loc.rstrip('/')}/{dir_relative}"
        backend_rel = self._rel(abs_path)
        content_type = "application/x-directory"

        await self.storage.write_bytes(backend_rel, b"", content_type)

        from app.catalog.db_models import UnifiedCatalogVolumeFile
        existing = (
            db.query(UnifiedCatalogVolumeFile)
            .filter(
                UnifiedCatalogVolumeFile.volume_id == volume_id,
                UnifiedCatalogVolumeFile.file_path == dir_relative,
            )
            .first()
        )
        if not existing:
            entry = UnifiedCatalogVolumeFile(
                volume_id=volume_id,
                file_path=dir_relative,
                file_name=dir_name + "/",
                size_bytes=0,
                content_type=content_type,
                uploaded_by=uploaded_by,
            )
            db.add(entry)
            db.commit()

        logger.info("Created directory %s in volume %s", dir_relative, volume_id)
        return FileInfo(
            file_path=dir_relative,
            file_name=dir_name + "/",
            size_bytes=0,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
        )

    async def list_files(self, db: Session, volume_id: str) -> list[FileInfo]:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")

        # 1. Fetch files indexed in Postgres DB table
        from app.catalog.db_models import UnifiedCatalogVolumeFile
        db_files = (
            db.query(UnifiedCatalogVolumeFile)
            .filter(UnifiedCatalogVolumeFile.volume_id == volume_id)
            .all()
        )

        files_by_path: dict[str, FileInfo] = {}
        for db_file in db_files:
            clean_path = db_file.file_path.lstrip("/")
            if not clean_path or clean_path == ".keep" or clean_path.endswith("/.keep"):
                continue
            files_by_path[clean_path] = FileInfo(
                file_path=clean_path,
                file_name=db_file.file_name or clean_path.split("/")[-1],
                size_bytes=db_file.size_bytes or 0,
                content_type=db_file.content_type or "application/octet-stream",
                last_modified=db_file.uploaded_at or datetime.now(timezone.utc),
            )

        # 2. Try listing raw files from storage backend and merge
        try:
            base_loc = self._get_base_loc(volume)
            rel_base_loc = self._rel(base_loc)
            raw_files = await self.storage.list_files(rel_base_loc)

            prefix = rel_base_loc.rstrip("/") + "/" if rel_base_loc else ""

            for f in raw_files:
                f_path = f.file_path
                if prefix and f_path.startswith(prefix):
                    f_path = f_path[len(prefix):]
                elif rel_base_loc and f_path.startswith(rel_base_loc):
                    f_path = f_path[len(rel_base_loc):].lstrip("/")

                f_path = f_path.lstrip("/")

                if not f_path or f_path == ".keep" or f_path.endswith("/.keep"):
                    continue

                if f_path not in files_by_path:
                    files_by_path[f_path] = FileInfo(
                        file_path=f_path,
                        file_name=f.file_name or f_path.split("/")[-1],
                        size_bytes=f.size_bytes,
                        content_type=f.content_type,
                        last_modified=f.last_modified,
                    )
                else:
                    existing = files_by_path[f_path]
                    if f.size_bytes and not existing.size_bytes:
                        existing.size_bytes = f.size_bytes
                    if f.last_modified:
                        existing.last_modified = f.last_modified
                    if f.content_type and existing.content_type == "application/octet-stream":
                        existing.content_type = f.content_type
        except Exception as exc:
            logger.warning("Failed to list files from storage backend for volume %s: %s", volume_id, exc)

        return sorted(files_by_path.values(), key=lambda x: x.file_path.lower())

    async def download_file(self, db: Session, volume_id: str, file_path: str) -> tuple[bytes, str]:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")
        base_loc = self._get_base_loc(volume)
        abs_path = f"{base_loc.rstrip('/')}/{file_path.strip('/')}".strip("/")
        data = await self.storage.read_bytes(self._rel(abs_path))
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return data, content_type

    async def get_download_url(
        self, db: Session, volume_id: str, file_path: str, expiry_seconds: int = 3600
    ) -> str:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")
        base_loc = self._get_base_loc(volume)
        abs_path = f"{base_loc.rstrip('/')}/{file_path.strip('/')}".strip("/")
        return await self.storage.get_url(self._rel(abs_path), expiry_seconds)

    async def delete_file(self, db: Session, volume_id: str, file_path: str) -> None:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")
        base_loc = self._get_base_loc(volume)
        abs_path = f"{base_loc.rstrip('/')}/{file_path.strip('/')}".strip("/")
        await self.storage.delete(self._rel(abs_path))

        from app.catalog.db_models import UnifiedCatalogVolumeFile
        db.query(UnifiedCatalogVolumeFile).filter(
            UnifiedCatalogVolumeFile.volume_id == volume_id,
            UnifiedCatalogVolumeFile.file_path == file_path.lstrip("/"),
        ).delete(synchronize_session=False)
        db.commit()
        logger.info("Deleted %s from volume %s", file_path, volume_id)

    async def rename_file(self, db: Session, volume_id: str, old_path: str, new_name: str) -> FileInfo:
        volume = db.query(UnifiedCatalogVolume).filter(UnifiedCatalogVolume.id == volume_id).first()
        if not volume:
            raise ValueError(f"Volume {volume_id} not found")
        
        base_loc = self._get_base_loc(volume)
        old_abs = f"{base_loc.rstrip('/')}/{old_path.strip('/')}"
        
        is_dir = old_path.endswith('/')
        old_parts = old_path.strip('/').split('/')
        old_parts[-1] = new_name
        new_path = "/".join(old_parts)
        if is_dir:
            new_path += "/"
            old_abs += "/"
            
        new_abs = f"{base_loc.rstrip('/')}/{new_path.strip('/')}"
        if is_dir:
            new_abs += "/"
        
        # Read/write/delete in blob storage
        try:
            data = await self.storage.read_bytes(self._rel(old_abs))
            content_type = "application/x-directory" if is_dir else mimetypes.guess_type(new_name)[0] or "application/octet-stream"
            await self.storage.write_bytes(self._rel(new_abs), data, content_type)
            await self.storage.delete(self._rel(old_abs))
        except Exception:
            # If it's a directory, there might not be a direct blob, or we might need to move all nested.
            # For simplicity in this prototype, we'll try to move the .keep blob if it exists.
            keep_old = self._rel(old_abs.rstrip('/') + "/.keep")
            keep_new = self._rel(new_abs.rstrip('/') + "/.keep")
            try:
                data = await self.storage.read_bytes(keep_old)
                await self.storage.write_bytes(keep_new, data, "application/x-directory")
                await self.storage.delete(keep_old)
            except Exception:
                pass # ignore

        # Update DB
        from app.catalog.db_models import UnifiedCatalogVolumeFile
        files = db.query(UnifiedCatalogVolumeFile).filter(
            UnifiedCatalogVolumeFile.volume_id == volume_id,
            UnifiedCatalogVolumeFile.file_path.like(f"{old_path}%")
        ).all()
        
        for f in files:
            f.file_path = f.file_path.replace(old_path, new_path, 1)
            if f.file_path == new_path:
                f.file_name = new_name + ("/" if is_dir else "")
        db.commit()

        logger.info("Renamed %s to %s in volume %s", old_path, new_path, volume_id)
        return FileInfo(
            file_path=new_path,
            file_name=new_name + ("/" if is_dir else ""),
            size_bytes=0,
            content_type="application/x-directory" if is_dir else None,
            last_modified=datetime.now(timezone.utc),
        )
