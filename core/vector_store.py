"""ChromaDB vector store for semantic memory search."""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DIR = Path(__file__).parent.parent / "storage" / "chroma"


class VectorStore:
    """ChromaDB wrapper for semantic search."""

    def __init__(self) -> None:
        self._collection = None
        self._embed_fn = None

    @property
    def available(self) -> bool:
        return self._collection is not None and self._embed_fn is not None

    def initialize(self) -> None:
        """Initialize ChromaDB and embedding model."""
        try:
            import chromadb
            from chromadb.config import Settings

            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name="memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialized (%d vectors)", self._collection.count())
        except Exception as e:
            logger.warning("ChromaDB unavailable: %s", e)
            self._collection = None

        if self._collection is not None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embed_fn = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence-transformers embedding model loaded")
            except Exception as e:
                logger.warning("Embedding model unavailable: %s", e)
                self._embed_fn = None

    def store_document(
        self, content: str, role: str, conversation_id: str, doc_id: str = ""
    ) -> None:
        """Store a document in ChromaDB."""
        if not self.available or len(content.strip()) < 10:
            return
        if not doc_id:
            doc_id = f"{conversation_id}_{uuid.uuid4().hex[:8]}"
        embedding = self._embed_fn.encode(content[:1000]).tolist()
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content[:2000]],
            metadatas=[{
                "role": role,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        )

    def store_summary(
        self, messages: list[dict], conversation_id: str
    ) -> None:
        """Condense messages into a summary and store."""
        if not self.available or not messages:
            return
        parts = []
        for msg in messages:
            content = msg.get("content", "")[:300]
            if content.strip():
                parts.append(f"{msg.get('role', '?')}: {content}")
        summary = "\n".join(parts)[:2000]
        if not summary.strip():
            return
        doc_id = f"summary_{conversation_id}_{uuid.uuid4().hex[:8]}"
        self.store_document(summary, "summary", conversation_id, doc_id)
        logger.info("Auto-summarized %d messages into ChromaDB", len(messages))

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search in ChromaDB."""
        if not self.available or self._collection.count() == 0:
            return []
        query_embedding = self._embed_fn.encode(query[:500]).tolist()
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
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
