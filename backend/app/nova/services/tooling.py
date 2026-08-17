from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NovaToolResult:
    ok: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseNovaTool(ABC):
    key: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        raise NotImplementedError

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.key,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
