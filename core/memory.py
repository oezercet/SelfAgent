"""Layered memory system for SelfAgent.

Layer 1: Short-term — in-memory buffer, flushed to SQLite.
Layer 2: Long-term — semantic search via ChromaDB + sentence-transformers.
Layer 3: User profile — key/value pairs in SQLite.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
DB_PATH = STORAGE_DIR / "memory.db"
CHROMA_DIR = STORAGE_DIR / "chroma"

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
        self._chroma_collection = None
        self._embed_fn = None

    async def initialize(self) -> None:
        """Create storage directory, open DB, run migrations, init ChromaDB."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(DB_PATH))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("Memory initialized (db=%s)", DB_PATH)

        # Initialize ChromaDB for semantic search
        try:
            import chromadb
            from chromadb.config import Settings

            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            self._chroma_collection = client.get_or_create_collection(
                name="memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB initialized (%d vectors)",
                self._chroma_collection.count(),
            )
        except Exception as e:
            logger.warning("ChromaDB unavailable, falling back to keyword search: %s", e)
            self._chroma_collection = None

        # Initialize embedding model (lazy — loaded on first use)
        if self._chroma_collection is not None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embed_fn = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence-transformers embedding model loaded")
            except Exception as e:
                logger.warning("Embedding model unavailable: %s", e)
                self._embed_fn = None

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ── Short-term (Layer 1) ─────────────────────────

    def add(self, role: str, content: str, metadata: dict | None = None) -> None:
        """Add a message to the short-term buffer."""
        self._messages.append(
            {"role": role, "content": content, "metadata": metadata or {}}
        )
        self._trim()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return all messages in the short-term buffer."""
        return list(self._messages)

    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        """Return the N most recent messages."""
        return self._messages[-count:]

    def clear(self) -> None:
        """Clear the short-term buffer (does not delete from DB)."""
        self._messages.clear()
        self._conversation_id = uuid.uuid4().hex[:12]

    def _trim(self) -> None:
        """Keep only the last max_short_term messages.

        When auto_summarize is enabled, overflow messages are condensed
        into a summary and stored in ChromaDB for future semantic retrieval.
        """
        if len(self._messages) <= self.max_short_term:
            return

        overflow = self._messages[:-self.max_short_term]
        self._messages = self._messages[-self.max_short_term:]

        # Auto-summarize overflowing messages into ChromaDB
        if self.auto_summarize and self._chroma_collection and self._embed_fn:
            try:
                self._store_summary(overflow)
            except Exception as e:
                logger.debug("Auto-summarize failed: %s", e)

    def _store_summary(self, messages: list[dict]) -> None:
        """Condense a batch of messages into a summary and store in ChromaDB."""
        if not messages:
            return

        # Build a compact summary from the overflow messages
        parts = []
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:300]
            if content.strip():
                parts.append(f"{role}: {content}")

        summary = "\n".join(parts)
        if not summary.strip():
            return

        # Truncate to reasonable size for embedding
        summary = summary[:2000]
        doc_id = f"summary_{self._conversation_id}_{uuid.uuid4().hex[:8]}"

        embedding = self._embed_fn.encode(summary[:1000]).tolist()
        self._chroma_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[{
                "role": "summary",
                "conversation_id": self._conversation_id,
                "message_count": str(len(messages)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        )
        logger.info(
            "Auto-summarized %d messages into ChromaDB (id=%s)",
            len(messages), doc_id,
        )

    # ── Persistence ──────────────────────────────────

    async def save_message(
        self, role: str, content: str, metadata: dict | None = None
    ) -> None:
        """Persist a message to SQLite and ChromaDB."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO memory (role, content, conversation_id, metadata) "
            "VALUES (?, ?, ?, ?)",
            (role, content, self._conversation_id, json.dumps(metadata or {})),
        )
        await self._db.commit()

        # Store in ChromaDB for semantic search
        if self._chroma_collection is not None and self._embed_fn is not None:
            # Skip very short or tool-generated content
            if len(content.strip()) < 10:
                return
            try:
                doc_id = f"{self._conversation_id}_{uuid.uuid4().hex[:8]}"
                embedding = self._embed_fn.encode(content[:1000]).tolist()
                self._chroma_collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content[:2000]],
                    metadatas=[{
                        "role": role,
                        "conversation_id": self._conversation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                )
            except Exception as e:
                logger.debug("ChromaDB insert error: %s", e)

    async def load_recent_conversations(self, limit: int = 50) -> list[dict]:
        """Load the most recent messages from SQLite."""
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
        """Simple keyword search in past messages."""
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
        """Search for semantically relevant past context using ChromaDB.

        Uses sentence-transformers embeddings for cosine similarity search.
        Falls back to keyword search if ChromaDB is unavailable.
        """
        if self._chroma_collection is None or self._embed_fn is None:
            return await self.search_history(query, limit=top_k)

        if self._chroma_collection.count() == 0:
            return []

        try:
            query_embedding = self._embed_fn.encode(query[:500]).tolist()
            results = self._chroma_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._chroma_collection.count()),
            )

            memories = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    memories.append({
                        "role": meta.get("role", "unknown"),
                        "content": doc,
                        "timestamp": meta.get("timestamp", ""),
                    })
            return memories
        except Exception as e:
            logger.warning("ChromaDB search error, falling back to keyword: %s", e)
            return await self.search_history(query, limit=top_k)

    # ── User profile (Layer 3) ───────────────────────

    async def set_profile(self, key: str, value: str) -> None:
        """Set a user profile value."""
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
        """Get a single profile value."""
        if not self._db:
            return None
        cursor = await self._db.execute(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def get_user_profile(self) -> dict[str, str]:
        """Get the full user profile."""
        if not self._db:
            return {}
        cursor = await self._db.execute("SELECT key, value FROM user_profile")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    async def get_message_count(self) -> int:
        """Get total number of stored messages."""
        if not self._db:
            return 0
        cursor = await self._db.execute("SELECT COUNT(*) as cnt FROM memory")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
