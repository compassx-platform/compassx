"""GitHub implementation of GitProvider."""

from __future__ import annotations

from typing import Any

from app.agents.services.agent.tools.providers.base_provider import GitProvider


class GitHubProvider(GitProvider):

    # ── Pull request operations ───────────────────────────────────────────────

    def create_pr(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        pr = repo.create_pull(
            title=args["title"],
            body=args.get("description", ""),
            head=args["branch"],
            base=args.get("base_branch", "main"),
            draft=args.get("draft", False),
        )
        return {"url": pr.html_url, "number": pr.number}

    def post_pr_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        pr = repo.get_pull(args["pr_number"])
        comment = pr.create_issue_comment(args["message"])
        return {"comment_id": comment.id}

    def set_pr_ready(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        pr = repo.get_pull(args["pr_number"])
        pr.edit(draft=False)
        return {"status": "ready", "url": pr.html_url}

    # ── Work item / issue operations ──────────────────────────────────────────

    def post_workitem_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        issue = repo.get_issue(args["workitem_id"])
        comment = issue.create_comment(args["message"])
        return {"comment_id": comment.id}

    def update_workitem_status(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        issue = repo.get_issue(args["workitem_id"])
        state = (
            "closed"
            if args.get("state", "").lower() in ("done", "closed", "resolved")
            else "open"
        )
        issue.edit(state=state)
        return {"state": state, "url": issue.html_url}

    # ── Diff fetching ─────────────────────────────────────────────────────────

    def fetch_pr_diff(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        try:
            from github import Github
        except ImportError:
            raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")

        g = Github(token) if token else Github()
        repo = g.get_repo(args["repo"])
        pr = repo.get_pull(args["pr_number"])
        diffs = [{"filename": f.filename, "patch": f.patch or ""} for f in pr.get_files()]
        return {"diffs": diffs[:20]}
