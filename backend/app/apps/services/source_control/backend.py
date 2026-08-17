"""SourceControlBackend — abstract base class for all source control backends.

Mirrors the BlobStorageBackend pattern from app.storage.backend.
Both the native (content-addressable) and git backends implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class FileDiff:
    path: str
    status: str                     # 'added' | 'modified' | 'deleted'
    diff_lines: list[str] = field(default_factory=list)  # line-level diff, computed on demand


class SourceControlBackend(ABC):
    """
    All operations are async.
    Implementations must be safe to construct per-request (no long-lived state
    other than DB session + blob backend references).
    """

    @abstractmethod
    async def create_branch(
        self,
        app_id: uuid.UUID,
        name: str,
        from_branch_id: Optional[uuid.UUID],
        created_by: uuid.UUID,
    ):
        """Create a new branch, optionally forked from an existing branch.

        For the native backend: materialize the source branch's head commit
        onto the new branch's working path.
        For the git backend: create a real git branch on the remote.

        Returns the new AppBranch ORM instance.
        """
        ...

    @abstractmethod
    async def checkpoint(
        self,
        branch_id: uuid.UUID,
        message: str,
        author: str,
    ):
        """Snapshot the current working tree of the branch's pod.

        Native backend:
          - Scan working tree → hash each file → upload new blobs (skip if hash exists)
          - Build tree manifest JSON → hash + store manifest blob
          - Insert app_commits row → update app_branches.head_commit_id

        Git backend:
          - Stage all → commit → push to remote
          - Insert app_commits row mirroring the git commit SHA

        Returns the new AppCommit ORM instance.
        """
        ...

    @abstractmethod
    async def materialize(
        self,
        commit_id: uuid.UUID,
        target_path: str,
    ) -> None:
        """Restore a commit's file tree to `target_path` on disk.

        Native backend: read tree manifest → fetch blobs by hash → write files.
        Git backend: git checkout the commit SHA into target_path.

        Used for:
          - Branch creation (materialize source branch head onto new PVC)
          - Revert (re-materialize old commit over current working tree)
          - Production pod startup (materialize chosen commit)
        """
        ...

    @abstractmethod
    async def diff(
        self,
        commit_a: uuid.UUID,
        commit_b: uuid.UUID,
        include_line_diff: bool = False,
    ) -> list[FileDiff]:
        """Compare two commits and return changed file paths.

        Hash-comparison first (fast); line-level diff computed on demand
        from blob contents only when include_line_diff=True.
        No diff stored — always computed live.
        """
        ...

    @abstractmethod
    async def get_head(self, branch_id: uuid.UUID):
        """Return the AppCommit at HEAD of the given branch, or None if no commits."""
        ...
