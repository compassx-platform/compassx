"""Git Workspace tool — clone a repo, create a branch, and set up a git worktree.

Intended as the first tool Claude calls before modifying any code.
Returns the worktree path so subsequent tools (claude_agent, python_code, etc.)
can be directed at the isolated workspace.

Workflow:
  1. Clone the repository (shallow, into a temp base dir) if not already present
  2. Fetch latest and create a new branch from the base branch
  3. Add a git worktree for that branch at a deterministic path
  4. Return all workspace metadata so Claude knows where to work

The clone is cached by repo URL under the agent's workspace root so repeated
calls for the same repo don't re-clone from scratch — they just fetch + new branch.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.auth.pat_resolver import get_pat
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Base directory where all agent clones are stored.
# Override with AGENT_WORKSPACE_ROOT env var.
_DEFAULT_WORKSPACE_ROOT = Path(tempfile.gettempdir()) / "agent_workspaces"


def _workspace_root() -> Path:
    root = Path(os.environ.get("AGENT_WORKSPACE_ROOT", str(_DEFAULT_WORKSPACE_ROOT)))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_dir_name(url: str) -> str:
    """Convert a repo URL to a filesystem-safe directory name.

    Includes org+project info so repos with the same name in different
    organisations don't collide.
    e.g. https://dev.azure.com/IpPlatform/IDCC/_git/myrepo → IpPlatform_IDCC_myrepo
    """
    # Strip scheme and trailing slashes
    path = url.split("://", 1)[-1].rstrip("/")
    # Remove .git suffix from last segment
    path = re.sub(r"\.git$", "", path)
    # Replace non-word chars with underscores
    safe = re.sub(r"[^\w.-]", "_", path)
    # Collapse multiple underscores and trim to 80 chars
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe[:80] or "repo"


def _run(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict | None = None,
    label: str = "",
) -> tuple[int, str, str]:
    """Run a subprocess, log the command and result, return (rc, stdout, stderr)."""
    tag = f"[{label}] " if label else ""
    logger.debug("%sgit cmd: %s  (cwd=%s)", tag, " ".join(cmd), cwd or ".")

    # Mask any PAT in the logged command
    logged_cmd = " ".join(
        re.sub(r"(https?://)([^@]+@)", r"\1***@", part) for part in cmd
    )
    logger.debug("%sRunning: %s", tag, logged_cmd)

    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        timeout=300,
    )
    if result.stdout.strip():
        logger.debug("%sstdout: %s", tag, result.stdout.strip()[:500])
    if result.stderr.strip():
        level = logging.WARNING if result.returncode != 0 else logging.DEBUG
        logger.log(level, "%sstderr: %s", tag, result.stderr.strip()[:500])
    logger.debug("%src=%d", tag, result.returncode)
    return result.returncode, result.stdout.strip(), result.stderr.strip()



def _inject_pat_into_url(url: str, pat: str, provider: str) -> str:
    """Embed PAT credentials into the clone URL for HTTPS auth."""
    if not pat:
        logger.warning("No PAT available — clone may fail for private repos")
        return url
    # Already has credentials embedded
    if "@" in url.split("://", 1)[-1]:
        logger.debug("URL already contains credentials — not injecting PAT")
        return url
    if provider == "azure_devops":
        # ADO requires empty username: https://:{pat}@dev.azure.com/...
        auth_url = url.replace("https://", f"https://:{pat}@", 1)
    else:
        # GitHub: https://x-access-token:<pat>@github.com/...
        auth_url = url.replace("https://", f"https://x-access-token:{pat}@", 1)
    logger.debug("Auth URL constructed for provider=%s (PAT injected)", provider)
    return auth_url


class GitWorkspaceTool(BaseTool):
    key = "git_workspace"
    name = "Git Workspace Setup"
    description = (
        "Clone a Git repository, create a new branch, and set up an isolated git worktree. "
        "Always call this tool first before reading or modifying any repository code. "
        "Returns the worktree_path to use as the working directory for all subsequent file "
        "operations and code changes."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": (
                    "Full HTTPS clone URL of the repository. "
                    "e.g. https://github.com/org/repo.git or "
                    "https://dev.azure.com/org/project/_git/repo"
                ),
            },
            "branch_name": {
                "type": "string",
                "description": (
                    "Name of the new branch to create for this work. "
                    "e.g. 'feature/add-login' or 'fix/null-pointer'. "
                    "Must be a valid git branch name."
                ),
            },
            "base_branch": {
                "type": "string",
                "description": "Branch to base the new branch on. Defaults to 'main'.",
            },
            "provider": {
                "type": "string",
                "enum": ["github", "azure_devops"],
                "description": "Git provider. Used to select the correct PAT for authentication.",
            },
            "shallow": {
                "type": "boolean",
                "description": (
                    "If true (default), perform a shallow clone (depth=1) for speed. "
                    "Set to false if full history is needed."
                ),
            },
        },
        "required": ["repo_url", "branch_name"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        repo_url: str = args["repo_url"]
        branch_name: str = args["branch_name"]
        base_branch: str = args.get("base_branch", "main")
        provider: str = args.get("provider", "github")
        shallow: bool = args.get("shallow", True)

        logger.info(
            "git_workspace START — repo=%s branch=%s base=%s provider=%s shallow=%s",
            repo_url, branch_name, base_branch, provider, shallow,
        )

        # Validate branch name
        if not re.match(r"^[\w./\-]+$", branch_name):
            return ToolResult(ok=False, error=f"Invalid branch name: '{branch_name}'")

        pat = get_pat(agent, provider)
        auth_url = _inject_pat_into_url(repo_url, pat, provider)

        repo_dir_name = _safe_dir_name(repo_url)
        clone_base = _workspace_root() / repo_dir_name

        logger.info("Clone base directory: %s", clone_base)

        # ── Step 1: clone or fetch ─────────────────────────────────────────────
        if (clone_base / ".git").exists():
            logger.info("STEP 1: Repo already cloned at %s — running git fetch", clone_base)
            rc, out, err = _run(
                ["git", "fetch", "--all", "--prune"],
                cwd=clone_base,
                label="fetch",
            )
            if rc != 0:
                logger.error("git fetch failed (rc=%d): %s", rc, err)
                return ToolResult(ok=False, error=f"git fetch failed: {err}")
            logger.info("STEP 1: fetch OK")
        else:
            logger.info("STEP 1: Cloning %s → %s", repo_url, clone_base)
            # --no-single-branch ensures all remote branches are available locally
            # (needed so we can create new branches off any base_branch)
            clone_cmd = ["git", "clone", "--no-single-branch"]
            if shallow:
                clone_cmd += ["--depth", "1"]
            clone_cmd += ["--branch", base_branch, auth_url, str(clone_base)]

            try:
                rc, out, err = _run(clone_cmd, label="clone")
            except subprocess.TimeoutExpired:
                return ToolResult(ok=False, error="git clone timed out after 300 seconds")

            if rc != 0:
                logger.warning(
                    "Clone with --branch %s failed (rc=%d: %s) — retrying without --branch",
                    base_branch, rc, err,
                )
                # Retry without --branch (let git use the default branch)
                clone_cmd_bare = ["git", "clone", "--no-single-branch"]
                if shallow:
                    clone_cmd_bare += ["--depth", "1"]
                clone_cmd_bare += [auth_url, str(clone_base)]
                try:
                    rc2, _, err2 = _run(clone_cmd_bare, label="clone-bare")
                except subprocess.TimeoutExpired:
                    return ToolResult(ok=False, error="git clone timed out after 300 seconds")
                if rc2 != 0:
                    logger.error("Bare clone also failed (rc=%d): %s", rc2, err2)
                    return ToolResult(ok=False, error=f"git clone failed: {err2}")
                logger.info("STEP 1: bare clone OK")
            else:
                logger.info("STEP 1: clone OK")

        # ── Step 2: ensure base branch exists locally and create new branch ───
        logger.info("STEP 2: Setting up branch '%s' from '%s'", branch_name, base_branch)

        # List existing branches for debug and fallback detection
        rc_lb, local_branches, _ = _run(["git", "branch", "-a"], cwd=clone_base, label="branch-list")
        logger.info("Available branches:\n%s", local_branches)

        # Auto-detect default branch if the requested base_branch doesn't exist
        def _branch_exists(name: str) -> bool:
            return any(
                b.strip().lstrip("* ").replace("remotes/origin/", "") == name
                for b in local_branches.splitlines()
            )

        if not _branch_exists(base_branch):
            # Try common default branch names, then fall back to whatever HEAD points at
            for candidate in ("development", "develop", "master", "main"):
                if candidate != base_branch and _branch_exists(candidate):
                    logger.warning(
                        "Base branch '%s' not found — falling back to '%s'",
                        base_branch, candidate,
                    )
                    base_branch = candidate
                    break
            else:
                # Last resort: ask git what the remote HEAD is
                rc_head, remote_head, _ = _run(
                    ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                    cwd=clone_base, label="remote-head",
                )
                if rc_head == 0 and remote_head:
                    detected = remote_head.strip().replace("refs/remotes/origin/", "")
                    logger.warning("Using remote HEAD branch: %s", detected)
                    base_branch = detected
                else:
                    logger.error(
                        "Cannot determine default branch. Available: %s", local_branches
                    )
                    return ToolResult(
                        ok=False,
                        error=(
                            f"Base branch '{base_branch}' not found and could not auto-detect default. "
                            f"Available branches: {local_branches}"
                        ),
                    )

        # Check out base branch
        rc, _, err = _run(["git", "checkout", base_branch], cwd=clone_base, label="checkout-base")
        if rc != 0:
            logger.warning("checkout %s failed — trying to create tracking branch from origin", base_branch)
            rc, _, err = _run(
                ["git", "checkout", "-b", base_branch, f"origin/{base_branch}"],
                cwd=clone_base,
                label="checkout-track",
            )
            if rc != 0:
                logger.error("Could not check out base branch '%s': %s", base_branch, err)
                return ToolResult(
                    ok=False,
                    error=(
                        f"Could not check out base branch '{base_branch}': {err}\n"
                        f"Available branches: {local_branches}"
                    ),
                )

        # Pull latest (non-fatal — shallow clones can't always pull)
        rc_pull, _, err_pull = _run(
            ["git", "pull", "--ff-only", "origin", base_branch],
            cwd=clone_base,
            label="pull",
        )
        if rc_pull != 0:
            logger.warning("git pull non-fatal warning: %s", err_pull)

        # Create new branch (idempotent — ignore "already exists")
        rc, _, err = _run(
            ["git", "branch", branch_name, base_branch],
            cwd=clone_base,
            label="create-branch",
        )
        if rc != 0:
            if "already exists" in err:
                logger.info("Branch '%s' already exists — reusing", branch_name)
            else:
                logger.error("Could not create branch '%s': %s", branch_name, err)
                return ToolResult(ok=False, error=f"Could not create branch '{branch_name}': {err}")
        else:
            logger.info("STEP 2: branch '%s' created OK", branch_name)

        # ── Step 3: add a worktree for the new branch ─────────────────────────
        safe_branch = branch_name.replace("/", "_").replace("\\", "_")
        worktree_path = _workspace_root() / f"{repo_dir_name}__{safe_branch}"
        logger.info("STEP 3: Setting up worktree at %s", worktree_path)

        # If the directory already exists, git worktree add will refuse.
        # Remove it first so we can re-add cleanly.
        if worktree_path.exists():
            logger.debug("Worktree path already exists — pruning stale entries and removing dir")
            _run(["git", "worktree", "prune"], cwd=clone_base, label="wt-prune")
            try:
                shutil.rmtree(worktree_path)
                logger.debug("Removed stale worktree dir: %s", worktree_path)
            except Exception as exc:
                logger.warning("Could not remove stale worktree dir: %s", exc)

        rc, _, err = _run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            cwd=clone_base,
            label="wt-add",
        )
        if rc != 0:
            logger.error("git worktree add failed (rc=%d): %s", rc, err)
            return ToolResult(ok=False, error=f"git worktree add failed: {err}")

        logger.info("STEP 3: worktree OK at %s", worktree_path)

        # ── Step 4: collect metadata ───────────────────────────────────────────
        _, head_sha, _ = _run(["git", "rev-parse", "HEAD"], cwd=worktree_path, label="head-sha")
        # Return the public URL (without embedded PAT)
        _, remote_url, _ = _run(["git", "remote", "get-url", "origin"], cwd=clone_base, label="remote-url")
        public_url = re.sub(r"(https?://):[^@]*@", r"\1", remote_url) if remote_url else repo_url

        logger.info(
            "git_workspace DONE — worktree=%s branch=%s head=%s",
            worktree_path, branch_name, head_sha[:8] if head_sha else "?",
        )

        return ToolResult(
            ok=True,
            result={
                "worktree_path": str(worktree_path),
                "clone_path": str(clone_base),
                "branch": branch_name,
                "base_branch": base_branch,
                "head_commit": head_sha,
                "repo_url": public_url,
                "message": (
                    f"Workspace ready. Use worktree_path='{worktree_path}' as the "
                    f"working directory for all file operations on branch '{branch_name}'."
                ),
            },
        )
