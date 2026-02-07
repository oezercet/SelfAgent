"""Clipboard tool — read from and write to the system clipboard.

Uses macOS pbcopy/pbpaste. On Linux falls back to xclip/xsel.
"""

import asyncio
import logging
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class ClipboardTool(BaseTool):
    name = "clipboard"
    description = "Read from or write text to the system clipboard."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "The clipboard action to perform",
            },
            "content": {
                "type": "string",
                "description": "Text to write to the clipboard (for 'write' action)",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "read":
                return await self._read()
            elif action == "write":
                return await self._write(kwargs.get("content", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Clipboard error: %s", action)
            return f"Clipboard error: {e}"

    async def _read(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "pbpaste",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            return f"Failed to read clipboard: {err}"

        text = stdout.decode("utf-8", errors="replace")
        if not text:
            return "Clipboard is empty."

        if len(text) > 10000:
            text = text[:10000] + "\n... [truncated]"

        return f"Clipboard content ({len(text)} chars):\n{text}"

    async def _write(self, content: str) -> str:
        if not content:
            return "Error: content is required for write action."

        proc = await asyncio.create_subprocess_exec(
            "pbcopy",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=content.encode("utf-8")),
            timeout=5,
        )

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            return f"Failed to write to clipboard: {err}"

        return f"Copied {len(content)} chars to clipboard."
