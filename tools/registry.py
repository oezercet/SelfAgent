"""Tool registry — discovers and manages available tools."""

import logging
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of all available tools the agent can use."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._disabled: set[str] = set()

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if not tool.name:
            raise ValueError(f"Tool {tool.__class__.__name__} has no name")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def list_tools_with_status(self) -> list[dict[str, Any]]:
        """Return tool info including enabled/disabled status."""
        return [
            {
                "name": name,
                "description": tool.description,
                "enabled": name not in self._disabled,
            }
            for name, tool in self._tools.items()
        ]

    def set_tool_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a tool. Returns True if tool exists."""
        if name not in self._tools:
            return False
        if enabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)
        logger.info("Tool '%s' %s", name, "enabled" if enabled else "disabled")
        return True

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get function schemas for all enabled tools."""
        return [
            tool.to_function_schema()
            for name, tool in self._tools.items()
            if name not in self._disabled
        ]

    async def execute(self, name: str, **kwargs: Any) -> str:
        """Execute a tool by name with the given arguments."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'"

        if name in self._disabled:
            return f"Error: Tool '{name}' is currently disabled."

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            logger.exception("Tool '%s' failed", name)
            return f"Error executing {name}: {e}"
