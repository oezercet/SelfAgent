"""Screenshot tool — capture screen or specific windows.

Uses macOS `screencapture` command. On Linux falls back to
`import` (ImageMagick) or `gnome-screenshot`.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage" / "screenshots"


class ScreenshotTool(BaseTool):
    name = "screenshot"
    description = (
        "Capture screenshots: take a full-screen screenshot or "
        "capture a specific application window."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["take_screenshot", "capture_window"],
                "description": "The screenshot action to perform",
            },
            "window_name": {
                "type": "string",
                "description": "Name of the window to capture (for 'capture_window')",
            },
            "output_path": {
                "type": "string",
                "description": "File path to save the screenshot (optional)",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "take_screenshot":
                return await self._take_screenshot(kwargs.get("output_path", ""))
            elif action == "capture_window":
                return await self._capture_window(
                    kwargs.get("window_name", ""),
                    kwargs.get("output_path", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Screenshot error: %s", action)
            return f"Screenshot error: {e}"

    def _default_path(self) -> Path:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return STORAGE_DIR / f"screenshot_{ts}.png"

    async def _take_screenshot(self, output_path: str) -> str:
        path = Path(output_path).expanduser() if output_path else self._default_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # macOS screencapture
        proc = await asyncio.create_subprocess_exec(
            "screencapture", "-x", str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            return f"Screenshot failed: {err}"

        if path.exists():
            size_kb = path.stat().st_size / 1024
            return f"Screenshot saved to {path} ({size_kb:.1f} KB)"
        return "Screenshot failed: file not created."

    async def _capture_window(self, window_name: str, output_path: str) -> str:
        if not window_name:
            return "Error: window_name is required for capture_window."

        path = Path(output_path).expanduser() if output_path else self._default_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use AppleScript to find window ID then screencapture -l
        script = (
            f'tell application "System Events" to tell process "{window_name}" '
            f"to set wid to id of window 1"
        )
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0:
            # Fallback: interactive window capture
            proc2 = await asyncio.create_subprocess_exec(
                "screencapture", "-x", "-w", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc2.communicate(), timeout=15)
            if path.exists():
                size_kb = path.stat().st_size / 1024
                return (
                    f"Could not find window '{window_name}' by name. "
                    f"Used interactive capture instead. Saved to {path} ({size_kb:.1f} KB)"
                )
            return f"Could not capture window '{window_name}'."

        window_id = stdout.decode().strip()
        proc3 = await asyncio.create_subprocess_exec(
            "screencapture", "-x", "-l", window_id, str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc3.communicate(), timeout=10)

        if path.exists():
            size_kb = path.stat().st_size / 1024
            return f"Captured window '{window_name}' to {path} ({size_kb:.1f} KB)"
        return f"Failed to capture window '{window_name}'."
