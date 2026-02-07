"""Persistent task tracking with SQLite.

Tasks survive restarts and are injected into the agent's system prompt
so it never forgets active work.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
DB_PATH = STORAGE_DIR / "tasks.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    context TEXT,
    priority INTEGER DEFAULT 0,
    due_date TEXT,
    parent_task_id INTEGER,
    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""


@dataclass
class Task:
    """A tracked task."""

    id: int
    description: str
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    due_date: str | None = None
    parent_task_id: int | None = None


class TaskManager:
    """SQLite-backed task manager."""

    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database and create tables."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(DB_PATH))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("TaskManager initialized (db=%s)", DB_PATH)

    async def close(self) -> None:
        """Close the database."""
        if self._db:
            await self._db.close()
            self._db = None

    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        """Convert a database row to a Task."""
        return Task(
            id=row["id"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            context=json.loads(row["context"] or "{}"),
            priority=row["priority"],
            due_date=row["due_date"],
            parent_task_id=row["parent_task_id"],
        )

    async def create(
        self,
        description: str,
        priority: int = 0,
        parent_task_id: int | None = None,
        context: dict | None = None,
        due_date: str | None = None,
    ) -> Task:
        """Create a new task."""
        if not self._db:
            raise RuntimeError("TaskManager not initialized")

        cursor = await self._db.execute(
            "INSERT INTO tasks (description, priority, parent_task_id, context, due_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (description, priority, parent_task_id, json.dumps(context or {}), due_date),
        )
        await self._db.commit()
        task_id = cursor.lastrowid

        logger.info("Created task #%d: %s", task_id, description)
        return await self.get(task_id)

    async def get(self, task_id: int) -> Task | None:
        """Get a task by ID."""
        if not self._db:
            return None
        cursor = await self._db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return self._row_to_task(row) if row else None

    async def update_status(self, task_id: int, status: str) -> Task | None:
        """Update a task's status."""
        if not self._db:
            return None
        await self._db.execute(
            "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, task_id),
        )
        await self._db.commit()
        logger.info("Task #%d -> %s", task_id, status)
        return await self.get(task_id)

    async def update(self, task_id: int, **kwargs: Any) -> Task | None:
        """Update task fields."""
        if not self._db:
            return None
        allowed = {"description", "status", "priority", "due_date", "context"}
        sets = []
        values = []
        for key, val in kwargs.items():
            if key not in allowed:
                continue
            if key == "context":
                val = json.dumps(val)
            sets.append(f"{key} = ?")
            values.append(val)

        if not sets:
            return await self.get(task_id)

        sets.append("updated_at = datetime('now')")
        values.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?"
        await self._db.execute(sql, values)
        await self._db.commit()
        return await self.get(task_id)

    async def get_active(self) -> list[Task]:
        """Get all active tasks ordered by priority."""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE status = 'active' ORDER BY priority DESC, id ASC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def get_by_status(self, status: str) -> list[Task]:
        """Get tasks by status."""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, id ASC",
            (status,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def get_all(self) -> list[Task]:
        """Get all tasks."""
        if not self._db:
            return []
        cursor = await self._db.execute("SELECT * FROM tasks ORDER BY id DESC")
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def get_subtasks(self, parent_id: int) -> list[Task]:
        """Get subtasks of a parent task."""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY id ASC",
            (parent_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def delete(self, task_id: int) -> bool:
        """Delete a task."""
        if not self._db:
            return False
        await self._db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await self._db.commit()
        return True

    async def format_active_tasks(self) -> str:
        """Format active tasks for system prompt injection."""
        tasks = await self.get_active()
        if not tasks:
            return "No active tasks."
        lines = []
        for t in tasks:
            priority = "HIGH" if t.priority >= 2 else "NORMAL" if t.priority >= 0 else "LOW"
            lines.append(f"{t.id}. [{priority}] {t.description} — Status: {t.status}")
        return "\n".join(lines)
