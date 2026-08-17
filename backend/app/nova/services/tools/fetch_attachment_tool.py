"""FetchAttachmentTool — server-side tool allowing Nova to inspect tool_fetch attachments."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

# Import directly from the module file (NOT via package __init__) to avoid circular imports.
# tools/__init__.py imports registry.py which imports this file — using the package
# import would trigger that cycle during module initialization.
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult  # noqa: E402
from app.models.agents import Agent


class FetchAttachmentTool(BaseTool):
    """Tool allowing Nova to search or inspect line slices of a tool_fetch file attachment."""

    key = "fetch_attachment"
    name = "Fetch Attachment"
    description = (
        "Retrieve extracted text content or search lines from a large session file attachment. "
        "Accepts file_id, optional query substring to filter matching lines, optional page number, and optional line_start / line_end indices."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The UUID of the session file attachment to fetch.",
            },
            "query": {
                "type": "string",
                "description": "Optional keyword or substring to filter lines.",
            },
            "page": {
                "type": ["integer", "string"],
                "description": "Optional 1-based page number to fetch specific PDF page (e.g. 1, 2) or 'all'.",
            },
            "line_start": {
                "type": "integer",
                "description": "Optional 1-based line number to start reading from.",
            },
            "line_end": {
                "type": "integer",
                "description": "Optional 1-based line number to end reading at.",
            },
        },
        "required": ["file_id"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        from app.nova.services.attachment_service import fetch_attachment_content

        file_id = args.get("file_id")
        if not file_id:
            return ToolResult(ok=False, error="file_id is required")

        query = args.get("query")
        page = args.get("page")
        line_start = args.get("line_start")
        line_end = args.get("line_end")

        content = fetch_attachment_content(
            file_id=file_id,
            query=query,
            line_start=line_start,
            line_end=line_end,
            page=page,
            db=db,
        )

        if content.startswith("Error:"):
            return ToolResult(ok=False, error=content)

        return ToolResult(
            ok=True,
            result={
                "file_id": str(file_id),
                "query": query,
                "line_start": line_start,
                "line_end": line_end,
                "content": content,
            },
        )
