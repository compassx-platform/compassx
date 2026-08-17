"""RAG search tool."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class RagSearchTool(BaseTool):
    key = "rag_search"
    name = "RAG Document Search"
    description = "Search uploaded documents using semantic similarity."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "top_k": {"type": "integer", "description": "Number of chunks to return", "default": 5},
        },
        "required": ["query"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            from app.services.document_processor import search_documents

            results = search_documents(query=args["query"], top_k=args.get("top_k", 5), db=db)
            return ToolResult(ok=True, result={"chunks": results})
        except ImportError:
            return ToolResult(ok=False, error="RAG dependencies (pgvector, sentence-transformers) not installed.")
