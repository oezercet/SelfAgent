"""System control tool — interact with the operating system.

Supports querying system info, opening applications,
listing/killing processes. Uses subprocess for macOS commands.
"""

import asyncio
import logging
import platform
import shutil
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)

# Commands that are too dangerous to run
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){", "fork bomb",
    "sudo rm", "chmod -R 777 /", "shutdown", "reboot", "halt",
}


class SystemControlTool(BaseTool):
    name = "system_control"
    description = (
        "Control the operating system: run shell commands, get system info, "
        "open applications, list running processes, and kill processes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "run_command",
                    "get_system_info",
                    "open_application",
                    "list_processes",
                    "kill_process",
                ],
                "description": "The system action to perform",
            },
            "command": {
                "type": "string",
                "description": "Shell command to execute (for 'run_command')",
            },
            "app_name": {
                "type": "string",
                "description": "Application name or path (for 'open_application')",
            },
            "pid": {
                "type": "integer",
                "description": "Process ID (for 'kill_process')",
            },
        },
        "required": ["action"],
    }
    requires_confirmation = True

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "run_command":
                return await self._run_command(kwargs.get("command", ""))
            elif action == "get_system_info":
                return await self._get_system_info()
            elif action == "open_application":
                return await self._open_application(kwargs.get("app_name", ""))
            elif action == "list_processes":
                return await self._list_processes()
            elif action == "kill_process":
                return await self._kill_process(kwargs.get("pid", 0))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("System control error: %s", action)
            return f"System error: {e}"

    async def _run_command(self, command: str) -> str:
        if not command:
            return "Error: command is required."

        # Safety check
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return f"Error: Command blocked for safety: {command}"

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out (30s): {command}"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            err = stderr.decode("utf-8", errors="replace").strip()
            if err:
                output += f"\n[stderr] {err}"

        if len(output) > 10000:
            output = output[:10000] + "\n... [truncated]"

        return f"$ {command}\n{output.strip()}" if output.strip() else f"$ {command}\n(no output)"

    async def _get_system_info(self) -> str:
        info = {
            "OS": f"{platform.system()} {platform.release()}",
            "Version": platform.version(),
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "Python": platform.python_version(),
        }

        # Disk usage
        total, used, free = shutil.disk_usage("/")
        info["Disk Total"] = f"{total / (1024**3):.1f} GB"
        info["Disk Used"] = f"{used / (1024**3):.1f} GB"
        info["Disk Free"] = f"{free / (1024**3):.1f} GB"

        # Memory (macOS)
        try:
            proc = await asyncio.create_subprocess_exec(
                "sysctl", "-n", "hw.memsize",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            mem_bytes = int(stdout.decode().strip())
            info["RAM"] = f"{mem_bytes / (1024**3):.1f} GB"
        except Exception:
            pass

        # CPU count
        try:
            proc = await asyncio.create_subprocess_exec(
                "sysctl", "-n", "hw.ncpu",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            info["CPU Cores"] = stdout.decode().strip()
        except Exception:
            pass

        # Uptime
        try:
            proc = await asyncio.create_subprocess_exec(
                "uptime",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            info["Uptime"] = stdout.decode().strip()
        except Exception:
            pass

        lines = ["System Information:\n"]
        for key, value in info.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    async def _open_application(self, app_name: str) -> str:
        if not app_name:
            return "Error: app_name is required."

        # macOS: use 'open -a'
        proc = await asyncio.create_subprocess_exec(
            "open", "-a", app_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            return f"Failed to open '{app_name}': {err}"

        return f"Opened application: {app_name}"

    async def _list_processes(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "ps", "aux", "--sort=-%mem",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # macOS ps doesn't support --sort, use different format
            proc = await asyncio.create_subprocess_shell(
                "ps aux | head -30",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

        output = stdout.decode("utf-8", errors="replace")
        lines = output.strip().split("\n")
        if len(lines) > 30:
            lines = lines[:30]
            lines.append(f"... showing top 30 processes")

        return "\n".join(lines)

    async def _kill_process(self, pid: int) -> str:
        if not pid:
            return "Error: pid is required."

        proc = await asyncio.create_subprocess_exec(
            "kill", str(pid),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            return f"Failed to kill process {pid}: {err}"

        return f"Sent SIGTERM to process {pid}"
