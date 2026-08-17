"""Base tool — all agent tools must inherit from this class.

Provides a SOLID-compliant contract:
  - Single Responsibility: each subclass handles exactly one tool capability
  - Open/Closed: add new tools by subclassing, never by editing the dispatcher
  - Liskov Substitution: every tool can be used interchangeably via BaseTool
  - Interface Segregation: tools only implement what they need (execute)
  - Dependency Inversion: orchestrator depends on BaseTool, not concrete classes
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent


@dataclass
class ToolResult:
    """Standardised return value from every tool execution."""

    ok: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Subclasses must define:
      - key          : unique tool identifier (matches LLM tool_call name)
      - name         : human-readable label shown in Agent Builder
      - description  : passed to the LLM as the tool's description
      - is_async     : True  → call execute_async (I/O-bound, runs in thread)
                       False → call execute (CPU-bound or trivially fast)
      - input_schema : JSON Schema object describing accepted arguments

    All tools receive the full execution context so they can access
    the agent, database session, or other shared state when needed.
    """

    # ── Class-level metadata (override in subclasses) ──────────────────────────
    key: str
    name: str
    description: str
    is_async: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)

    # ── Execution interface ────────────────────────────────────────────────────

    @abstractmethod
    def execute(
        self,
        args: dict[str, Any],
        agent: Agent,
        db: Session,
    ) -> ToolResult:
        """Execute the tool synchronously.

        Raises NotImplementedError by default for async-only tools that
        override execute_async instead.
        """

    # ── LLM integration helpers ───────────────────────────────────────────────

    def to_openai_definition(self) -> dict[str, Any]:
        """Return an OpenAI-compatible tool definition dict."""
        return {
            "type": "function",
            "function": {
                "name": self.key,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
