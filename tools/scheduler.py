"""Scheduler tool -- schedule one-time and recurring tasks.

Uses asyncio for lightweight in-process scheduling.
Tasks are stored in JSON for persistence across restarts.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.cron_parser import cron_matches, parse_cron, parse_interval

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"

_EXPR_HELP = (
    "  Interval: 'every 5m', 'every 2h', 'every 1d'\n"
    "  Cron: '*/5 * * * *' (min hour dom month dow)"
)


class SchedulerTool(BaseTool):
    name = "scheduler"
    description = (
        "Schedule tasks: run once at a specific time, set up recurring jobs, "
        "list all scheduled tasks, and cancel pending ones."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "schedule_once", "schedule_recurring",
                    "list_scheduled", "cancel_scheduled",
                ],
                "description": "The scheduling action to perform",
            },
            "task_description": {
                "type": "string",
                "description": "Description of the task to schedule",
            },
            "run_at": {
                "type": "string",
                "description": "ISO 8601 datetime for one-time execution (for 'schedule_once')",
            },
            "cron_expression": {
                "type": "string",
                "description": "Interval ('every 5m/2h/1d') or standard cron ('*/5 * * * *' = every 5 min)",
            },
            "task_id": {
                "type": "string",
                "description": "Task identifier (for 'cancel_scheduled')",
            },
            "command": {
                "type": "string",
                "description": "Shell command to execute when the task triggers",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._handles: dict[str, asyncio.Task] = {}
        self._db_path = STORAGE_DIR / "scheduler.json"

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        try:
            if action == "schedule_once":
                return await self._schedule_once(
                    kwargs.get("task_description", ""),
                    kwargs.get("run_at", ""),
                    kwargs.get("command", ""),
                )
            elif action == "schedule_recurring":
                return await self._schedule_recurring(
                    kwargs.get("task_description", ""),
                    kwargs.get("cron_expression", ""),
                    kwargs.get("command", ""),
                )
            elif action == "list_scheduled":
                return self._list_scheduled()
            elif action == "cancel_scheduled":
                return self._cancel_scheduled(kwargs.get("task_id", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Scheduler error: %s", action)
            return f"Scheduler error: {e}"

    async def _schedule_once(self, description: str, run_at: str, command: str) -> str:
        if not run_at:
            return "Error: run_at (ISO 8601 datetime) is required."
        if not command and not description:
            return "Error: command or task_description is required."
        try:
            target_time = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
        except ValueError:
            return f"Error: Invalid datetime format: {run_at}. Use ISO 8601."

        now = datetime.now(timezone.utc)
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        delay = (target_time - now).total_seconds()
        if delay < 0:
            return "Error: run_at is in the past."

        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = {
            "id": task_id, "type": "once",
            "description": description or command, "command": command,
            "run_at": run_at, "status": "pending",
            "created_at": now.isoformat(),
        }
        self._save()
        self._handles[task_id] = asyncio.create_task(
            self._run_once(task_id, delay, command))
        return (
            f"Scheduled task '{task_id}'\n"
            f"  Description: {description or command}\n"
            f"  Runs at: {run_at}\n"
            f"  Delay: {delay:.0f} seconds"
        )

    async def _schedule_recurring(self, description: str, cron_expr: str, command: str) -> str:
        if not cron_expr:
            return f"Error: cron_expression is required.\n{_EXPR_HELP}"
        if not command and not description:
            return "Error: command or task_description is required."

        interval = parse_interval(cron_expr)
        is_cron = False
        if interval is None:
            cron_fields = parse_cron(cron_expr)
            if cron_fields is None:
                return f"Error: Invalid expression '{cron_expr}'.\n{_EXPR_HELP}"
            is_cron = True

        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        task_info = {
            "id": task_id, "type": "recurring",
            "description": description or command, "command": command,
            "cron_expression": cron_expr, "is_cron": is_cron,
            "status": "active", "created_at": now.isoformat(),
            "run_count": 0,
        }
        if not is_cron:
            task_info["interval_seconds"] = interval
        self._tasks[task_id] = task_info
        self._save()

        if is_cron:
            handle = asyncio.create_task(self._run_cron(task_id, cron_expr, command))
            schedule_info = f"Cron: {cron_expr}"
        else:
            handle = asyncio.create_task(self._run_recurring(task_id, interval, command))
            schedule_info = f"Interval: {cron_expr} ({interval}s)"
        self._handles[task_id] = handle
        return (
            f"Scheduled recurring task '{task_id}'\n"
            f"  Description: {description or command}\n"
            f"  {schedule_info}\n"
            f"  Status: active"
        )

    def _list_scheduled(self) -> str:
        if not self._tasks:
            return "No scheduled tasks."
        lines = ["Scheduled tasks:\n"]
        for tid, task in self._tasks.items():
            status = task.get("status", "unknown")
            desc = task.get("description", "")
            ttype = task.get("type", "once")
            if ttype == "recurring":
                extra = f" (every {task.get('cron_expression', '?')}, runs: {task.get('run_count', 0)})"
            else:
                extra = f" (at {task.get('run_at', '?')})"
            lines.append(f"  [{status}] {tid}: {desc}{extra}")
        return "\n".join(lines)

    def _cancel_scheduled(self, task_id: str) -> str:
        if not task_id:
            return "Error: task_id is required."
        if task_id not in self._tasks:
            return f"Error: Task '{task_id}' not found."
        handle = self._handles.get(task_id)
        if handle and not handle.done():
            handle.cancel()
        self._tasks[task_id]["status"] = "cancelled"
        self._handles.pop(task_id, None)
        self._save()
        return f"Cancelled task '{task_id}'."

    @staticmethod
    async def _exec_command(command: str) -> None:
        """Execute a shell command with a 60-second timeout."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=60)

    def _mark_run(self, task_id: str) -> None:
        """Increment run_count and save."""
        if task_id in self._tasks:
            self._tasks[task_id]["run_count"] = self._tasks[task_id].get("run_count", 0) + 1
            self._save()

    def _mark_failed(self, task_id: str) -> None:
        """Mark a task as failed and save."""
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "failed"
            self._save()

    async def _run_once(self, task_id: str, delay: float, command: str) -> None:
        try:
            await asyncio.sleep(delay)
            if command:
                await self._exec_command(command)
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "completed"
                self._save()
            logger.info("Scheduled task %s completed", task_id)
        except asyncio.CancelledError:
            logger.info("Scheduled task %s was cancelled", task_id)
        except Exception:
            logger.exception("Scheduled task %s failed", task_id)
            self._mark_failed(task_id)

    async def _run_recurring(self, task_id: str, interval: float, command: str) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                if command:
                    await self._exec_command(command)
                self._mark_run(task_id)
                logger.info("Recurring task %s executed (run #%d)", task_id,
                            self._tasks.get(task_id, {}).get("run_count", 0))
        except asyncio.CancelledError:
            logger.info("Recurring task %s was cancelled", task_id)
        except Exception:
            logger.exception("Recurring task %s failed", task_id)
            self._mark_failed(task_id)

    async def _run_cron(self, task_id: str, cron_expr: str, command: str) -> None:
        """Run a task on a cron schedule by checking every 30 seconds."""
        try:
            last_run_minute = -1
            while True:
                await asyncio.sleep(30)
                now = datetime.now(timezone.utc)
                current_minute = now.minute + now.hour * 60 + now.day * 1440
                if current_minute == last_run_minute:
                    continue
                if cron_matches(cron_expr, now):
                    last_run_minute = current_minute
                    if command:
                        await self._exec_command(command)
                    self._mark_run(task_id)
                    logger.info("Cron task %s executed (run #%d)", task_id,
                                self._tasks.get(task_id, {}).get("run_count", 0))
        except asyncio.CancelledError:
            logger.info("Cron task %s was cancelled", task_id)
        except Exception:
            logger.exception("Cron task %s failed", task_id)
            self._mark_failed(task_id)

    def _save(self) -> None:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._db_path.write_text(
            json.dumps(self._tasks, indent=2, default=str), encoding="utf-8")

    def _load(self) -> None:
        if self._db_path.exists():
            data = json.loads(self._db_path.read_text(encoding="utf-8"))
            self._tasks = data
