"""Example plugin — demonstrates how to create a custom SelfAgent tool.

To create a plugin:
1. Create a .py file in this directory
2. Import BaseTool from tools.base
3. Create a class that extends BaseTool with:
   - name: unique tool identifier
   - description: what the tool does
   - parameters: JSON schema for arguments
   - execute(**kwargs) -> str: the implementation

The plugin loader will automatically discover and register your tool.
"""

from typing import Any

from tools.base import BaseTool


class HelloWorldTool(BaseTool):
    """A simple example plugin that greets the user."""

    name = "hello_world"
    description = "A simple greeting tool. Say hello to someone by name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name to greet",
            },
        },
        "required": ["name"],
    }

    async def execute(self, **kwargs: Any) -> str:
        name = kwargs.get("name", "World")
        return f"Hello, {name}! This is a plugin tool."
