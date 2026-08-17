"""Code generation pipeline.

Phase 0: Set up an isolated git worktree via GitWorkspaceTool.
Phase 1:  Build a context-rich prompt and hand it to Claude Code CLI.
          Claude Code runs inside the worktree directory and decides for
          itself how to explore the repo, what files to read/write, and
          how to commit and push the result.

The term *workspace* in this module always refers to the **git workspace**
(cloned repo + worktree) to avoid confusion with the agent's own execution
environment.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import ToolResult

logger = logging.getLogger(__name__)


def _setup_git_workspace(args: dict[str, Any], agent: Agent) -> ToolResult:
    """Clone the repo and create an isolated git worktree.

    Returns a ToolResult whose ``result`` dict contains at minimum:
      - ``worktree_path``
      - ``branch``
      - ``base_branch``
      - ``repo_url``
    """
    from app.agents.services.agent.tools.git_workspace_tool import GitWorkspaceTool

    repo_url: str = args.get("repo_url", "")
    repo: str = args.get("repo", "")
    org: str = args.get("organization", "")
    project: str = args.get("project", "")
    provider: str = args.get("provider", "github")

    if not repo_url and repo:
        if provider == "azure_devops" and org and project:
            repo_url = f"https://dev.azure.com/{org}/{project}/_git/{repo}"
        elif provider == "github":
            repo_url = f"https://github.com/{org}/{repo}.git" if org else f"https://github.com/{repo}.git"

    if not repo_url:
        return ToolResult(
            ok=False,
            error=(
                "No repo_url or repo provided. "
                "Pass repo_url (full HTTPS clone URL) or repo + organization + project."
            ),
        )

    branch_name: str = args.get("branch_name", "")
    if not branch_name:
        ticket = args.get("ticket_id") or args.get("workitem_id")
        if ticket:
            branch_name = f"feature/{ticket}"
        else:
            branch_name = f"agent/task-{int(time.time())}"

    logger.info("git_workspace setup — repo=%s branch=%s", repo_url, branch_name)

    ws_tool = GitWorkspaceTool()
    return ws_tool.execute(
        args={
            "repo_url": repo_url,
            "branch_name": branch_name,
            "base_branch": args.get("base_branch", "main"),
            "provider": provider,
            "shallow": True,
        },
        agent=agent,
        db=None,
    )


def run_generate_code(
    args: dict[str, Any],
    agent: Agent,
) -> ToolResult:
    """Execute the code-generation pipeline.

    Phase 0: clone + worktree setup (Python).
    Phase 1: hand the prompt to Claude Code CLI, which runs inside the
             worktree and autonomously reads, edits, commits, and pushes.

    Args:
        args:  Tool input arguments.
        agent: Agent ORM instance.
    """
    from app.agents.services.agent.tools.claude_agent.llm_invoker import invoke_claude_cli

    prompt = args.get("prompt")
    if not prompt:
        return ToolResult(ok=False, error="prompt is required for generate_code")

    # ── Phase 0: set up isolated git worktree ─────────────────────────────────
    git_worktree_path: str = args.get("worktree_path", "")

    # Reject bare strings (e.g. a branch name) that look like paths but aren't dirs
    if git_worktree_path and not Path(git_worktree_path).is_dir():
        logger.warning(
            "worktree_path='%s' is not an existing directory — running git workspace setup",
            git_worktree_path,
        )
        git_worktree_path = ""

    git_workspace_info: dict = {}

    if not git_worktree_path:
        ws_result = _setup_git_workspace(args, agent)
        if not ws_result.ok:
            return ToolResult(
                ok=False,
                error=f"Failed to set up git workspace: {ws_result.error}",
            )
        git_workspace_info = ws_result.result
        git_worktree_path = git_workspace_info["worktree_path"]
        # Propagate resolved values back so post-processing can read branch name etc.
        args = {
            **args,
            "worktree_path": git_worktree_path,
            "branch_name": git_workspace_info["branch"],
            "base_branch": git_workspace_info.get("base_branch", args.get("base_branch", "main")),
        }
        logger.info(
            "git workspace ready — worktree=%s branch=%s",
            git_worktree_path, git_workspace_info["branch"],
        )
    else:
        logger.info("git workspace setup skipped — worktree_path already provided: %s", git_worktree_path)

    # ── Phase 1+: build context-rich prompt ───────────────────────────────────
    branch = args.get("branch_name") or git_workspace_info.get("branch", "")
    repo_url_public = git_workspace_info.get("repo_url") or args.get("repo_url", "")

    git_workspace_preamble = (
        f"{'━' * 48}\n"
        f"GIT WORKSPACE READY — DO NOT CLONE OR CHECKOUT\n"
        f"{'━' * 48}\n"
        f"working_directory : {git_worktree_path}\n"
        f"branch            : {branch}\n"
        f"repo              : {repo_url_public}\n"
        f"{'━' * 48}\n\n"
        f"CRITICAL SETUP — READ BEFORE DOING ANYTHING:\n"
        f"- The repository is ALREADY cloned at: {git_worktree_path}\n"
        f"- Branch '{branch}' is ALREADY checked out. Do NOT run git clone, git checkout, or git switch.\n"
        f"- Start working immediately: read files, make changes, commit, push.\n\n"
        f"RULES:\n"
        f"1. ALL file reads and writes MUST use absolute paths inside: {git_worktree_path}\n"
        f"2. ALL git commands must be run with cwd={git_worktree_path} (use Bash with that directory)\n"
        f"3. Do NOT read or modify any files outside this directory.\n"
        f"4. Do NOT run git clone, git checkout, git switch, or git fetch.\n\n"
    )

    base_branch = args.get("base_branch", "main")
    pr_target = f"'{base_branch}' branch"

    if args.get("workitem_id"):
        suffix = (
            f"\n\nFINAL STEPS (do these after all code changes are complete):\n"
            f"1. Stage and commit all changes with a clear commit message.\n"
            f"2. Push branch '{branch}' to origin: git push --set-upstream origin {branch}\n"
            f"3. Create a Pull Request from '{branch}' targeting the {pr_target}.\n"
            f"4. Link the PR to work item #{args['workitem_id']}.\n"
        )
    else:
        suffix = (
            f"\n\nFINAL STEPS (do these after all code changes are complete):\n"
            f"1. Stage and commit all changes with a clear commit message.\n"
            f"2. Push branch '{branch}' to origin: git push --set-upstream origin {branch}\n"
            f"3. Create a Pull Request from '{branch}' targeting the {pr_target}.\n"
        )

    full_prompt = git_workspace_preamble + prompt + suffix
    logger.info("Claude CLI prompt suffix: %s", suffix.strip())

    # Hand off to Claude Code CLI. It runs inside the worktree, uses its own
    # native tools (Read, Write, Edit, Bash, git) to explore and modify the
    # repo, and decides the best strategy autonomously.
    return invoke_claude_cli(
        prompt=full_prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        args=args,
        agent=agent,
    )
