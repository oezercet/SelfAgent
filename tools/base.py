"""Abstract base class for all SelfAgent tools."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base class that all tools must extend."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    requires_confirmation: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return result as a string."""

    def to_function_schema(self) -> dict[str, Any]:
        """Convert to the unified function calling schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
