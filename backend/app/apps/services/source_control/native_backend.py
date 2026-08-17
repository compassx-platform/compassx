"""Native (content-addressable) source control backend.

Blob layout: apps/{app_id}/objects/{hash[:2]}/{hash}
Manifest layout: apps/{app_id}/manifests/{manifest_hash}
"""

import hashlib
import json
import os
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import AppBranch, AppCommit
from app.apps.services.source_control.backend import FileDiff, SourceControlBackend
from app.storage.backend import BlobStorageBackend


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob_path(app_id: uuid.UUID, file_hash: str) -> str:
    return f"apps/{app_id}/objects/{file_hash[:2]}/{file_hash}"


def _manifest_path(app_id: uuid.UUID, manifest_hash: str) -> str:
    return f"apps/{app_id}/manifests/{manifest_hash}"


class NativeSourceControlBackend(SourceControlBackend):
    """Content-addressable, immutable commit chain.

    No merge algorithm in v1 — branches are independent lineages.
    """

    def __init__(self, db: Session, blob: BlobStorageBackend):
        self._db = db
        self._blob = blob

    # ------------------------------------------------------------------
    # create_branch
    # ------------------------------------------------------------------

    async def create_branch(
        self,
        app_id: uuid.UUID,
        name: str,
        from_branch_id: Optional[uuid.UUID],
        created_by: uuid.UUID,
    ) -> AppBranch:
        head_commit_id: Optional[uuid.UUID] = None

        if from_branch_id is not None:
            source = (
                self._db.query(AppBranch)
                .filter(AppBranch.branch_id == from_branch_id, AppBranch.app_id == app_id)
                .one()
            )
            head_commit_id = source.head_commit_id

        branch = AppBranch(
            app_id=app_id,
            name=name,
            head_commit_id=head_commit_id,
            created_by=created_by,
        )
        self._db.add(branch)
        self._db.flush()
        return branch

    # ------------------------------------------------------------------
    # checkpoint
    # ------------------------------------------------------------------

    async def checkpoint(
        self,
        branch_id: uuid.UUID,
        message: str,
        author: str,
    ) -> AppCommit:
        branch = self._db.query(AppBranch).filter(AppBranch.branch_id == branch_id).one()
        app_id = branch.app_id

        # Fetch current working tree from pod via file service
        # The pod exposes a file listing endpoint; we call it here via HTTP.
        # In practice pod_service.get_working_tree_files(branch_id) returns
        # {relative_path: bytes} for all files under /backend and /frontend.
        from app.apps.services.file_service import get_working_tree_files
        file_map: dict[str, bytes] = await get_working_tree_files(branch_id)

        # Hash each file, upload blob if not already present
        path_hash_map: dict[str, str] = {}
        for rel_path, content in file_map.items():
            file_hash = _hash_bytes(content)
            path_hash_map[rel_path] = file_hash
            blob_key = _blob_path(app_id, file_hash)
            if not await self._blob.exists(blob_key):
                await self._blob.write_bytes(blob_key, content)

        # Build tree manifest: sorted for determinism
        manifest_data = json.dumps(
            {k: path_hash_map[k] for k in sorted(path_hash_map)},
            separators=(",", ":"),
        ).encode()
        manifest_hash = _hash_bytes(manifest_data)
        manifest_key = _manifest_path(app_id, manifest_hash)
        if not await self._blob.exists(manifest_key):
            await self._blob.write_bytes(manifest_key, manifest_data)

        # Insert commit row
        commit = AppCommit(
            app_id=app_id,
            parent_commit_id=branch.head_commit_id,
            author=author,
            message=message,
            tree_manifest_hash=manifest_hash,
        )
        self._db.add(commit)
        self._db.flush()

        # Advance branch HEAD
        branch.head_commit_id = commit.commit_id
        self._db.flush()

        return commit

    # ------------------------------------------------------------------
    # materialize
    # ------------------------------------------------------------------

    async def materialize(
        self,
        commit_id: uuid.UUID,
        target_path: str,
    ) -> None:
        commit = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_id).one()
        manifest_key = _manifest_path(commit.app_id, commit.tree_manifest_hash)
        manifest_data = await self._blob.read_bytes(manifest_key)
        path_hash_map: dict[str, str] = json.loads(manifest_data)

        for rel_path, file_hash in path_hash_map.items():
            blob_key = _blob_path(commit.app_id, file_hash)
            content = await self._blob.read_bytes(blob_key)
            abs_path = os.path.join(target_path, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as fh:
                fh.write(content)

    # ------------------------------------------------------------------
    # diff
    # ------------------------------------------------------------------

    async def diff(
        self,
        commit_a: uuid.UUID,
        commit_b: uuid.UUID,
        include_line_diff: bool = False,
    ) -> list[FileDiff]:
        async def _load_manifest(commit_id: uuid.UUID) -> dict[str, str]:
            c = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_id).one()
            key = _manifest_path(c.app_id, c.tree_manifest_hash)
            data = await self._blob.read_bytes(key)
            return json.loads(data)

        map_a = await _load_manifest(commit_a)
        map_b = await _load_manifest(commit_b)

        all_paths = set(map_a) | set(map_b)
        diffs: list[FileDiff] = []

        for path in sorted(all_paths):
            hash_a = map_a.get(path)
            hash_b = map_b.get(path)

            if hash_a is None:
                status = "added"
            elif hash_b is None:
                status = "deleted"
            elif hash_a != hash_b:
                status = "modified"
            else:
                continue  # unchanged

            diff_lines: list[str] = []
            if include_line_diff and status in ("added", "modified", "deleted"):
                commit_obj_a = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_a).one()
                import difflib
                
                if hash_a:
                    raw_a = await self._blob.read_bytes(_blob_path(commit_obj_a.app_id, hash_a))
                    lines_a = raw_a.decode(errors="replace").splitlines()
                else:
                    lines_a = []
                    
                if hash_b:
                    raw_b = await self._blob.read_bytes(_blob_path(commit_obj_a.app_id, hash_b))
                    lines_b = raw_b.decode(errors="replace").splitlines()
                else:
                    lines_b = []
                    
                diff_lines = list(difflib.unified_diff(lines_a, lines_b, fromfile=path, tofile=path))

            diffs.append(FileDiff(path=path, status=status, diff_lines=diff_lines))

        return diffs

    # ------------------------------------------------------------------
    # get_head
    # ------------------------------------------------------------------

    async def get_head(self, branch_id: uuid.UUID) -> Optional[AppCommit]:
        branch = self._db.query(AppBranch).filter(AppBranch.branch_id == branch_id).one_or_none()
        if branch is None or branch.head_commit_id is None:
            return None
        return self._db.query(AppCommit).filter(AppCommit.commit_id == branch.head_commit_id).one_or_none()
