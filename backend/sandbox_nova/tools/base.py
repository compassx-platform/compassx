"""Tool interface (open for extension, closed for modification)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NovaTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    def openai_definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> str:
        """Run the tool and return a string the model can read."""
