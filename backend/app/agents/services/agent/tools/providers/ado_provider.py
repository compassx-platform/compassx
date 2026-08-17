"""Azure DevOps implementation of GitProvider."""

from __future__ import annotations

import difflib
from typing import Any

from app.agents.services.agent.tools.providers.base_provider import GitProvider


def _ado_connection(org: str, token: str):
    from azure.devops.connection import Connection
    from msrest.authentication import BasicAuthentication

    creds = BasicAuthentication("", token)
    return Connection(base_url=f"https://dev.azure.com/{org}", creds=creds)


class AzureDevOpsProvider(GitProvider):

    # ── Pull request operations ───────────────────────────────────────────────

    def create_pr(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_1.git.models import GitPullRequest

        org = args.get("organization")
        if not org:
            raise ValueError("organization is required for azure_devops provider")

        conn = _ado_connection(org, token)
        git_client = conn.clients.get_git_client()

        source_ref = args["branch"]
        if not source_ref.startswith("refs/"):
            source_ref = f"refs/heads/{source_ref}"

        base_branch = args.get("base_branch", "main")
        if not base_branch.startswith("refs/"):
            base_branch = f"refs/heads/{base_branch}"

        pr = git_client.create_pull_request(
            git_pull_request_to_create=GitPullRequest(
                title=args["title"],
                description=args.get("description", ""),
                source_ref_name=source_ref,
                target_ref_name=base_branch,
                is_draft=args.get("draft", False),
            ),
            repository_id=args["repo"],
            project=args.get("project"),
        )
        org_url = (
            f"https://dev.azure.com/{org}/{args.get('project', '')}/"
            f"_git/{args['repo']}/pullrequest/{pr.pull_request_id}"
        )
        return {"url": org_url, "number": pr.pull_request_id}

    def post_pr_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_1.git.models import Comment, CommentThread

        org = args.get("organization")
        conn = _ado_connection(org, token)
        git_client = conn.clients.get_git_client()

        thread = git_client.create_thread(
            comment_thread=CommentThread(
                comments=[Comment(content=args["message"])],
                status="active",
            ),
            repository_id=args["repo"],
            pull_request_id=args["pr_number"],
            project=args.get("project"),
        )
        return {"thread_id": thread.id}

    def set_pr_ready(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_1.git.models import GitPullRequest

        org = args.get("organization")
        conn = _ado_connection(org, token)
        git_client = conn.clients.get_git_client()

        git_client.update_pull_request(
            git_pull_request_to_update=GitPullRequest(is_draft=False),
            repository_id=args["repo"],
            pull_request_id=args["pr_number"],
            project=args.get("project"),
        )
        return {"status": "ready"}

    # ── Work item / issue operations ──────────────────────────────────────────

    def post_workitem_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_1.work_item_tracking.models import CommentCreate

        org = args.get("organization")
        conn = _ado_connection(org, token)
        wit_client = conn.clients.get_work_item_tracking_client()

        comment = wit_client.add_comment(
            request=CommentCreate(text=args["message"]),
            project=args.get("project"),
            work_item_id=args["workitem_id"],
        )
        return {"comment_id": comment.id}

    def update_workitem_status(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

        org = args.get("organization")
        conn = _ado_connection(org, token)
        wit_client = conn.clients.get_work_item_tracking_client()

        patch = [
            JsonPatchOperation(
                op="add",
                path="/fields/System.State",
                value=args["state"],
            )
        ]
        wit_client.update_work_item(
            document=patch,
            id=args["workitem_id"],
            project=args.get("project"),
        )
        return {"state": args["state"]}

    # ── Diff fetching ─────────────────────────────────────────────────────────

    def fetch_pr_diff(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        from azure.devops.v7_0.git.models import GitVersionDescriptor

        org = args.get("organization")
        if not org:
            raise ValueError("organization is required for azure_devops provider")

        conn = _ado_connection(org, token)
        git_client = conn.clients.get_git_client()

        project = args.get("project")
        repo_id = args.get("repo")
        pr_id = args.get("pr_number")

        pr = git_client.get_pull_request(
            project=project, repository_id=repo_id, pull_request_id=pr_id
        )
        source_commit = pr.last_merge_source_commit.commit_id
        target_commit = pr.last_merge_target_commit.commit_id

        source_vd = GitVersionDescriptor(version=source_commit, version_type="commit")
        target_vd = GitVersionDescriptor(version=target_commit, version_type="commit")

        iterations = git_client.get_pull_request_iterations(
            repository_id=repo_id,
            pull_request_id=pr_id,
            project=project,
        )
        latest_iteration_id = iterations[-1].id

        changes = git_client.get_pull_request_iteration_changes(
            repository_id=repo_id,
            pull_request_id=pr_id,
            iteration_id=latest_iteration_id,
            project=project,
        )

        changed_files: list[tuple[str, Any]] = []
        for change in changes.change_entries or []:
            ap = change.additional_properties or {}
            item = ap.get("item") or {}
            path = item.get("path", "") if isinstance(item, dict) else getattr(item, "path", "")
            change_type = ap.get("changeType", "edit")
            is_folder = item.get("isFolder", False) if isinstance(item, dict) else False
            if path and not is_folder:
                changed_files.append((path, change_type))

        diffs = []
        for path, change_type in changed_files[:20]:
            try:
                def _read(vd, _path=path):
                    stream = git_client.get_item_content(
                        project=project,
                        repository_id=repo_id,
                        path=_path,
                        version_descriptor=vd,
                    )
                    return b"".join(stream).decode("utf-8", errors="replace")

                after = _read(source_vd).splitlines(keepends=True) if change_type not in ("delete", 32) else []
                before = _read(target_vd).splitlines(keepends=True) if change_type not in ("add", 1) else []

                patch = "".join(
                    difflib.unified_diff(before, after, fromfile=f"a{path}", tofile=f"b{path}", lineterm="")
                )
                diffs.append({"filename": path, "patch": patch or "<binary or identical>"})
            except Exception as exc:
                diffs.append({"filename": path, "patch": f"# Could not fetch diff: {exc}"})

        return {"diffs": diffs}
