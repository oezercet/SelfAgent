"""Layered memory system for SelfAgent.

Layer 1: Short-term — in-memory buffer, flushed to SQLite.
Layer 2: Long-term — semantic search via ChromaDB + sentence-transformers.
Layer 3: User profile — key/value pairs in SQLite.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from core.vector_store import VectorStore

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
DB_PATH = STORAGE_DIR / "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    conversation_id TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS user_profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memory_conversation
    ON memory(conversation_id);
CREATE INDEX IF NOT EXISTS idx_memory_timestamp
    ON memory(timestamp DESC);
"""


class Memory:
    """Persistent memory with short-term buffer, SQLite, and ChromaDB."""

    def __init__(self, max_short_term: int = 50, auto_summarize: bool = True) -> None:
        self.max_short_term = max_short_term
        self.auto_summarize = auto_summarize
        self._messages: list[dict[str, Any]] = []
        self._conversation_id: str = uuid.uuid4().hex[:12]
        self._db: aiosqlite.Connection | None = None
        self._vectors = VectorStore()

    async def initialize(self) -> None:
        """Create storage directory, open DB, run migrations, init ChromaDB."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(DB_PATH))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("Memory initialized (db=%s)", DB_PATH)
        self._vectors.initialize()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ── Short-term (Layer 1) ─────────────────────────

    def add(self, role: str, content: str, metadata: dict | None = None) -> None:
        self._messages.append(
            {"role": role, "content": content, "metadata": metadata or {}}
        )
        self._trim()

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        return self._messages[-count:]

    def clear(self) -> None:
        self._messages.clear()
        self._conversation_id = uuid.uuid4().hex[:12]

    def _trim(self) -> None:
        if len(self._messages) <= self.max_short_term:
            return
        overflow = self._messages[:-self.max_short_term]
        self._messages = self._messages[-self.max_short_term:]
        if self.auto_summarize and self._vectors.available:
            try:
                self._vectors.store_summary(overflow, self._conversation_id)
            except Exception as e:
                logger.debug("Auto-summarize failed: %s", e)

    # ── Persistence ──────────────────────────────────

    async def save_message(
        self, role: str, content: str, metadata: dict | None = None
    ) -> None:
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO memory (role, content, conversation_id, metadata) "
            "VALUES (?, ?, ?, ?)",
            (role, content, self._conversation_id, json.dumps(metadata or {})),
        )
        await self._db.commit()
        try:
            self._vectors.store_document(content, role, self._conversation_id)
        except Exception as e:
            logger.debug("ChromaDB insert error: %s", e)

    async def load_recent_conversations(self, limit: int = 50) -> list[dict]:
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT role, content, timestamp, metadata "
            "FROM memory ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "metadata": json.loads(row["metadata"] or "{}"),
            }
            for row in reversed(rows)
        ]

    async def search_history(self, query: str, limit: int = 10) -> list[dict]:
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT role, content, timestamp FROM memory "
            "WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = await cursor.fetchall()
        return [
            {"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]}
            for row in rows
        ]

    # ── Long-term semantic search (Layer 2) ──────────

    async def search_relevant(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._vectors.available:
            return await self.search_history(query, limit=top_k)
        try:
            return self._vectors.search(query, top_k)
        except Exception as e:
            logger.warning("ChromaDB search error: %s", e)
            return await self.search_history(query, limit=top_k)

    # ── User profile (Layer 3) ───────────────────────

    async def set_profile(self, key: str, value: str) -> None:
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO user_profile (key, value, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value),
        )
        await self._db.commit()

    async def get_profile(self, key: str) -> str | None:
        if not self._db:
            return None
        cursor = await self._db.execute(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def get_user_profile(self) -> dict[str, str]:
        if not self._db:
            return {}
        cursor = await self._db.execute("SELECT key, value FROM user_profile")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    async def get_message_count(self) -> int:
        if not self._db:
            return 0
        cursor = await self._db.execute("SELECT COUNT(*) as cnt FROM memory")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
