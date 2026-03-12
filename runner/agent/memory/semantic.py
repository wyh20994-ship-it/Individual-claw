"""
语义记忆 — 基于 ChromaDB 的向量检索
用于 RAG：将历史对话/文档嵌入向量库，对话时检索相关片段
"""

from __future__ import annotations
import os
from typing import Any

from utils.logger import logger


class SemanticMemory:
    def __init__(self, config: dict):
        self.config = config
        self.collection_name = config.get("collection", "hangclaw_mem")
        self._client = None
        self._collection = None

    async def initialize(self):
        try:
            import chromadb

            host = os.getenv("CHROMA_HOST", "127.0.0.1")
            port = int(os.getenv("CHROMA_PORT", "8000"))

            self._client = chromadb.HttpClient(host=host, port=port)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"[SemanticMemory] Connected to ChromaDB at {host}:{port}")
        except Exception as e:
            logger.warning(f"[SemanticMemory] ChromaDB unavailable, semantic memory disabled: {e}")
            self._collection = None

    async def add(self, text: str, metadata: dict | None = None):
        if not self._collection:
            return
        import uuid

        doc_id = str(uuid.uuid4())
        self._collection.add(documents=[text], ids=[doc_id], metadatas=[metadata or {}])

    async def query(self, text: str, top_k: int = 3) -> list[str]:
        if not self._collection:
            return []
        try:
            results = self._collection.query(query_texts=[text], n_results=top_k)
            return results.get("documents", [[]])[0]
        except Exception as e:
            logger.error(f"[SemanticMemory] Query failed: {e}")
            return []
