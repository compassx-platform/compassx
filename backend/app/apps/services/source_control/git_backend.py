"""Git thin-wrapper source control backend.

Branch = real git branch on the configured remote.
Commit = git commit SHA (stored in app_commits for CompassX-side bookkeeping).
"""

import subprocess
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import AppBranch, AppCommit, GitConfig
from app.apps.services.source_control.backend import FileDiff, SourceControlBackend


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class GitSourceControlBackend(SourceControlBackend):
    """Thin wrapper over real git operations against the configured git server.

    No custom merge logic — publish is a pointer switch, not a merge.
    """

    def __init__(self, db: Session, git_config: GitConfig, repo_base_path: str):
        self._db = db
        self._git_config = git_config
        # base path on the host where git repos are cloned, e.g. /git-repos/{app_id}
        self._repo_base = repo_base_path

    def _repo_path(self, app_id: uuid.UUID) -> str:
        import os
        return os.path.join(self._repo_base, str(app_id))

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
        repo_path = self._repo_path(app_id)
        from_ref = "main"

        if from_branch_id is not None:
            source = (
                self._db.query(AppBranch)
                .filter(AppBranch.branch_id == from_branch_id, AppBranch.app_id == app_id)
                .one()
            )
            from_ref = source.name

        # Create and push new git branch
        _run_git(["checkout", "-b", name, f"origin/{from_ref}"], cwd=repo_path)
        _run_git(["push", "origin", name], cwd=repo_path)

        # Resolve head SHA
        head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo_path)

        # Mirror git HEAD as an AppCommit row for uniform CompassX bookkeeping
        head_commit_id: Optional[uuid.UUID] = None
        if from_branch_id is not None:
            source_branch = (
                self._db.query(AppBranch)
                .filter(AppBranch.branch_id == from_branch_id)
                .one()
            )
            head_commit_id = source_branch.head_commit_id

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
        repo_path = self._repo_path(branch.app_id)

        # Stage, commit, push
        _run_git(["add", "-A"], cwd=repo_path)
        _run_git(
            ["commit", "--allow-empty", "-m", message, f"--author={author} <{author}>"],
            cwd=repo_path,
        )
        _run_git(["push", "origin", branch.name], cwd=repo_path)

        # Capture git SHA — use as tree_manifest_hash for the CompassX commit row
        git_sha = _run_git(["rev-parse", "HEAD"], cwd=repo_path)

        commit = AppCommit(
            app_id=branch.app_id,
            parent_commit_id=branch.head_commit_id,
            author=author,
            message=message,
            tree_manifest_hash=git_sha,  # git SHA serves as manifest identifier
        )
        self._db.add(commit)
        self._db.flush()

        branch.head_commit_id = commit.commit_id
        self._db.flush()

        return commit

    # ------------------------------------------------------------------
    # materialize
    # ------------------------------------------------------------------

    async def materialize(self, commit_id: uuid.UUID, target_path: str) -> None:
        commit = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_id).one()
        repo_path = self._repo_path(commit.app_id)
        git_sha = commit.tree_manifest_hash   # stored as git SHA for git backend

        # Checkout the specific SHA into target_path using git worktree / archive
        import os, shutil
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        os.makedirs(target_path, exist_ok=True)
        _run_git(["archive", "--format=tar", git_sha, "-o", "/tmp/_git_archive.tar"], cwd=repo_path)
        import tarfile
        with tarfile.open("/tmp/_git_archive.tar") as tf:
            tf.extractall(target_path)

    # ------------------------------------------------------------------
    # diff
    # ------------------------------------------------------------------

    async def diff(
        self,
        commit_a: uuid.UUID,
        commit_b: uuid.UUID,
        include_line_diff: bool = False,
    ) -> list[FileDiff]:
        ca = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_a).one()
        cb = self._db.query(AppCommit).filter(AppCommit.commit_id == commit_b).one()
        repo_path = self._repo_path(ca.app_id)
        sha_a = ca.tree_manifest_hash
        sha_b = cb.tree_manifest_hash

        # Name-status diff for changed files
        name_status = _run_git(["diff", "--name-status", sha_a, sha_b], cwd=repo_path)
        diffs: list[FileDiff] = []

        for line in name_status.splitlines():
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            status_char, path = parts[0], parts[1]
            status = {"A": "added", "D": "deleted", "M": "modified"}.get(status_char[0], "modified")

            diff_lines: list[str] = []
            if include_line_diff:
                raw = _run_git(["diff", sha_a, sha_b, "--", path], cwd=repo_path)
                diff_lines = raw.splitlines()

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
