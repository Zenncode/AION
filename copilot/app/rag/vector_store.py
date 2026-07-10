"""
AION Copilot — Qdrant Vector Store
====================================
Manages vector operations for RAG retrieval.
"""

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import settings

logger = logging.getLogger("aion-copilot.vector_store")


class VectorStore:
    """Thin wrapper around Qdrant for AION business context."""

    def __init__(self):
        if settings.qdrant_url:
            self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        else:
            self.client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    async def close(self):
        self.client.close()

    # --- Collection Management ---

    def ensure_collection(self, collection_name: str = None):
        """Create collection if it doesn't exist."""
        name = collection_name or settings.qdrant_collection
        collections = [c.name for c in self.client.get_collections().collections]

        if name not in collections:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20000,
                ),
            )
            logger.info("Created Qdrant collection: %s", name)
        else:
            logger.info("Collection exists: %s", name)

    def list_collections(self) -> List[str]:
        return [c.name for c in self.client.get_collections().collections]

    # --- Upsert ---

    def upsert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ):
        """
        Upsert document chunks with embeddings.

        documents: list of dicts with 'id', 'text', 'metadata' keys
        embeddings: parallel list of embedding vectors
        """
        self.ensure_collection(collection_name)

        points = []
        for doc, embedding in zip(documents, embeddings):
            points.append(
                PointStruct(
                    id=doc["id"],
                    vector=embedding,
                    payload={
                        "text": doc["text"],
                        "metadata": doc.get("metadata", {}),
                        "source": doc.get("metadata", {}).get("source", "unknown"),
                        "document_type": doc.get("metadata", {}).get("document_type", "unknown"),
                    },
                )
            )

        # Batch upsert (Qdrant handles batching internally)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch,
            )

        logger.info("Upserted %d points to collection '%s'", len(points), collection_name)

    # --- Search ---

    def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = None,
        score_threshold: float = None,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Semantic vector search with optional metadata filtering.

        Returns list of {'text', 'metadata', 'score'} dicts.
        """
        k = top_k or settings.rag_top_k
        threshold = score_threshold or settings.rag_score_threshold

        query_filter = None
        if filter_metadata:
            conditions = [
                FieldCondition(key=f"metadata.{k}", match=MatchValue(value=v))
                for k, v in filter_metadata.items()
            ]
            query_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k,
            score_threshold=threshold,
            query_filter=query_filter,
        )

        documents = []
        for hit in results:
            documents.append({
                "text": hit.payload.get("text", ""),
                "metadata": hit.payload.get("metadata", {}),
                "source": hit.payload.get("source", ""),
                "score": hit.score,
            })

        logger.info(
            "Search returned %d results (threshold=%.2f) from '%s'",
            len(documents), threshold, collection_name,
        )
        return documents

    # --- Delete ---

    def delete_by_source(self, collection_name: str, source: str):
        """Delete all points from a specific source document."""
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="source", match=MatchValue(value=source))
                    ]
                )
            ),
        )
        logger.info("Deleted points with source='%s' from '%s'", source, collection_name)

    def get_collection_info(self, collection_name: str) -> Dict:
        """Get collection stats."""
        info = self.client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }
