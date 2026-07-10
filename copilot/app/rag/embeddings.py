"""
AION Copilot — Embedding Service
==================================
Generates embeddings using OpenAI or local models.
"""

import logging
from typing import List

from app.core.config import settings

logger = logging.getLogger("aion-copilot.embeddings")


class EmbeddingService:
    """Generate embeddings for RAG retrieval."""

    def __init__(self):
        self._openai_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            import openai
            self._openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts using OpenAI text-embedding-3-small.
        Falls back to a simple hash-based embedding if API is unavailable.
        """
        if settings.openai_api_key:
            return self._embed_openai(texts)
        else:
            logger.warning("No OpenAI API key — using fallback embedding")
            return self._embed_fallback(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        return self.embed_texts([text])[0]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """OpenAI embedding API with batching."""
        client = self._get_openai_client()
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        logger.info("Embedded %d texts via OpenAI", len(texts))
        return all_embeddings

    def _embed_fallback(self, texts: List[str]) -> List[List[float]]:
        """
        Deterministic fallback embedding using hashing.
        Produces a fixed-dimension vector for each text.
        NOT semantically meaningful — only for dev/testing.
        """
        import hashlib
        import struct

        dim = settings.embedding_dimension
        embeddings = []

        for text in texts:
            # Use multiple hash rounds to fill the vector
            vector = []
            for i in range(0, dim, 4):
                h = hashlib.sha256(f"{text}_{i}".encode()).digest()
                # Unpack 4 floats from 16 bytes
                values = struct.unpack("4f", h[:16])
                vector.extend(values)
            # Normalize
            norm = sum(v ** 2 for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]
            embeddings.append(vector[:dim])

        return embeddings
