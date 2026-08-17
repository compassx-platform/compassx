"""Code review pipeline.

Fetches a PR diff via the provider API, asks the LLM to review it,
then posts the review back as a PR comment.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.agents import Agent
from app.agents.services.agent.tools.auth.pat_resolver import get_pat
from app.agents.services.agent.tools.base_tool import ToolResult
from app.agents.services.agent.tools.providers import get_provider

logger = logging.getLogger(__name__)


def run_code_review(
    args: dict[str, Any],
    agent: Agent,
    ask_llm_fn,
) -> ToolResult:
    """Execute the code-review pipeline.

    Args:
        args:       Tool input arguments.
        agent:      Agent ORM instance.
        ask_llm_fn: Callable(prompt, agent) -> ToolResult for text generation.
    """
    repo = args.get("repo")
    pr_number = args.get("pr_number")
    provider_name = args.get("provider", "github")

    if not repo or not pr_number:
        return ToolResult(ok=False, error="repo and pr_number are required for code_review")

    token = get_pat(agent, provider_name)
    provider = get_provider(provider_name)

    # Step 1 — fetch diff
    try:
        diff_data = provider.fetch_pr_diff(args, token)
    except Exception as exc:
        return ToolResult(ok=False, error=f"Failed to fetch PR diff: {exc}")

    if "error" in diff_data:
        return ToolResult(ok=False, error=diff_data["error"])

    diffs = diff_data.get("diffs", [])

    if not diffs:
        review_text = "No changed files found in this pull request."
    else:
        # Step 2 — ask LLM to review
        diff_text = "\n\n".join(
            f"### {d['filename']}\n```diff\n{d['patch']}\n```"
            for d in diffs[:20]
        )
        user_prompt = args.get("prompt", "")
        base_instruction = (
            f"You are a senior code reviewer. Review the following pull request diff "
            f"(PR #{pr_number}, repo '{repo}') and provide structured feedback covering: "
            "bugs/logic errors, security issues, code style, test coverage gaps, and "
            "improvement suggestions. Be concise and actionable.\n\n"
        )
        if user_prompt:
            base_instruction += f"Additional instructions: {user_prompt}\n\n"
        base_instruction += diff_text

        review_result = ask_llm_fn(base_instruction, agent)
        if not review_result.ok:
            return review_result
        review_text = review_result.result.get("output", "")

    # Step 3 — post review as PR comment
    comment_args = {
        "repo": repo,
        "pr_number": pr_number,
        "message": review_text,
        "provider": provider_name,
        "organization": args.get("organization"),
        "project": args.get("project"),
    }
    try:
        comment_result = provider.post_pr_comment(comment_args, token)
    except Exception as exc:
        return ToolResult(ok=False, error=f"Review generated but failed to post comment: {exc}")

    # Optionally comment on work item (non-fatal)
    if args.get("workitem_id"):
        try:
            wi_args = {
                "repo": repo,
                "workitem_id": args["workitem_id"],
                "message": f"Code review posted on PR #{pr_number}:\n\n{review_text[:2000]}",
                "organization": args.get("organization"),
                "project": args.get("project"),
            }
            provider.post_workitem_comment(wi_args, token)
        except Exception:
            pass

    return ToolResult(
        ok=True,
        result={
            "review": review_text,
            "comment_posted": comment_result,
            "files_reviewed": len(diffs),
        },
    )
