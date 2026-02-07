"""Terminal tool — persistent terminal sessions.

Supports running commands, keeping sessions open for dev servers,
interactive CLIs, and long-running processes.
"""

import asyncio
import logging
import time
from typing import Any

from core.config import get_config
from tools.base import BaseTool

logger = logging.getLogger(__name__)

# Session idle timeout (30 minutes)
SESSION_TIMEOUT = 30 * 60


class _Session:
    """A persistent terminal session."""

    def __init__(self, name: str, process: asyncio.subprocess.Process) -> None:
        self.name = name
        self.process = process
        self.last_used = time.time()
        self.output_buffer: list[str] = []

    @property
    def is_alive(self) -> bool:
        return self.process.returncode is None

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_used) > SESSION_TIMEOUT


class TerminalTool(BaseTool):
    """Run commands in persistent terminal sessions."""

    name = "terminal"
    description = (
        "Execute shell commands. Use 'run_command' for quick one-off commands. "
        "Use sessions for long-running processes (dev servers, builds). "
        "Commands run in the user's default shell."
    )
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "run_command",
                    "open_session",
                    "send_command",
                    "close_session",
                    "list_sessions",
                ],
                "description": "The terminal action to perform",
            },
            "command": {
                "type": "string",
                "description": "Command to execute (for run_command, send_command)",
            },
            "session_name": {
                "type": "string",
                "description": "Session name (for open/send/close_session)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (for run_command, default 30)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    async def execute(self, **kwargs: Any) -> str:
        """Execute a terminal action."""
        action = kwargs.get("action", "")

        # Clean up expired sessions
        self._cleanup_expired()

        try:
            if action == "run_command":
                return await self._run_command(
                    kwargs.get("command", ""),
                    kwargs.get("timeout", 30),
                )
            elif action == "open_session":
                return await self._open_session(kwargs.get("session_name", "default"))
            elif action == "send_command":
                return await self._send_command(
                    kwargs.get("session_name", ""),
                    kwargs.get("command", ""),
                )
            elif action == "close_session":
                return await self._close_session(kwargs.get("session_name", ""))
            elif action == "list_sessions":
                return self._list_sessions()
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Terminal action failed: %s", action)
            return f"Terminal error: {e}"

    async def _run_command(self, command: str, timeout: int) -> str:
        """Run a one-off command and return output."""
        if not command:
            return "Error: command is required."

        # Safety check
        config = get_config()
        for blocked in config.safety.blocked_commands:
            if blocked in command:
                return f"Blocked: '{command}' matches blocked command '{blocked}'"

        try:
            from pathlib import Path as _Path

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_Path.home()),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=min(timeout, 120)
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after {timeout}s: {command}"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")

        # Truncate very long output
        if len(output) > 10000:
            output = output[:10000] + "\n\n... [output truncated]"

        exit_code = proc.returncode
        return (
            f"$ {command}\n"
            f"Exit code: {exit_code}\n\n"
            f"{output.strip()}"
        )

    async def _open_session(self, name: str) -> str:
        """Open a named persistent session."""
        if name in self._sessions and self._sessions[name].is_alive:
            return f"Session '{name}' already exists and is active."

        proc = await asyncio.create_subprocess_shell(
            "bash",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._sessions[name] = _Session(name, proc)
        return f"Session '{name}' opened."

    async def _send_command(self, name: str, command: str) -> str:
        """Send a command to an existing session."""
        if not name:
            return "Error: session_name is required."
        if not command:
            return "Error: command is required."

        session = self._sessions.get(name)
        if not session or not session.is_alive:
            return f"Error: Session '{name}' not found or not running."

        # Safety check
        config = get_config()
        for blocked in config.safety.blocked_commands:
            if blocked in command:
                return f"Blocked: '{command}' matches blocked command '{blocked}'"

        session.last_used = time.time()

        # Write command and a marker to detect end of output
        marker = f"__SELFAGENT_DONE_{time.time_ns()}__"
        session.process.stdin.write(
            f"{command}\necho {marker}\n".encode()
        )
        await session.process.stdin.drain()

        # Read output until marker
        output_lines = []
        try:
            while True:
                line = await asyncio.wait_for(
                    session.process.stdout.readline(), timeout=30
                )
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if marker in decoded:
                    break
                output_lines.append(decoded)
        except asyncio.TimeoutError:
            output_lines.append("[output timed out after 30s]")

        output = "\n".join(output_lines)
        if len(output) > 10000:
            output = output[:10000] + "\n\n... [output truncated]"

        return f"[{name}] $ {command}\n{output}"

    async def _close_session(self, name: str) -> str:
        """Close a session."""
        if not name:
            return "Error: session_name is required."

        session = self._sessions.pop(name, None)
        if not session:
            return f"Session '{name}' not found."

        if session.is_alive:
            session.process.kill()
            await session.process.wait()
        return f"Session '{name}' closed."

    def _list_sessions(self) -> str:
        """List active sessions."""
        if not self._sessions:
            return "No active sessions."

        lines = ["Active sessions:\n"]
        for name, session in self._sessions.items():
            status = "running" if session.is_alive else "stopped"
            idle = int(time.time() - session.last_used)
            lines.append(f"  - {name}: {status} (idle {idle}s)")
        return "\n".join(lines)

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        expired = [
            name for name, s in self._sessions.items()
            if s.is_expired or not s.is_alive
        ]
        for name in expired:
            session = self._sessions.pop(name)
            if session.is_alive:
                session.process.kill()
            logger.info("Cleaned up expired session: %s", name)
