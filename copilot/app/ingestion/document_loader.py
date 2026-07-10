"""
AION Copilot — Document Ingestion
===================================
Chunks PDFs and table schemas, embeds them, and upserts into Qdrant.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.rag.vector_store import VectorStore
from app.rag.embeddings import EmbeddingService

logger = logging.getLogger("aion-copilot.ingestion")


class DocumentIngester:
    """Ingest documents into the Qdrant vector store."""

    def __init__(self):
        self.vector_store = VectorStore()
        self.embeddings = EmbeddingService()

    async def ingest(
        self,
        documents: List[str],
        collection_name: str = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> Dict:
        """
        Ingest a list of document paths into Qdrant.

        documents: list of file paths (PDFs, JSON schemas, text files)
        """
        collection = collection_name or settings.qdrant_collection
        all_chunks = []

        for doc_path in documents:
            path = Path(doc_path)

            if path.suffix.lower() == ".pdf":
                chunks = self._load_pdf(path, chunk_size, chunk_overlap)
            elif path.suffix.lower() in (".json", ".schema"):
                chunks = self._load_schema(path)
            elif path.suffix.lower() in (".md", ".txt", ".sql"):
                chunks = self._load_text(path, chunk_size, chunk_overlap)
            else:
                logger.warning("Unsupported file type: %s", path.suffix)
                continue

            all_chunks.extend(chunks)

        if not all_chunks:
            return {
                "documents_processed": 0,
                "chunks_created": 0,
                "collection_name": collection,
            }

        # Generate embeddings in batch
        texts = [c["text"] for c in all_chunks]
        embeddings = self.embeddings.embed_texts(texts)

        # Upsert to Qdrant
        self.vector_store.upsert_documents(
            collection_name=collection,
            documents=all_chunks,
            embeddings=embeddings,
        )

        result = {
            "documents_processed": len(documents),
            "chunks_created": len(all_chunks),
            "collection_name": collection,
        }

        logger.info(
            "Ingestion complete: %d docs → %d chunks → collection '%s'",
            len(documents), len(all_chunks), collection,
        )
        return result

    # --- PDF Ingestion ---

    def _load_pdf(
        self, path: Path, chunk_size: int, chunk_overlap: int
    ) -> List[Dict]:
        """Extract text from PDF and chunk it."""
        try:
            import pymupdf  # fitz
        except ImportError:
            import fitz as pymupdf

        doc = pymupdf.open(str(path))
        chunks = []

        full_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            full_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"

        doc.close()

        # Chunk the extracted text
        text_chunks = self._chunk_text(full_text, chunk_size, chunk_overlap)

        for i, chunk in enumerate(text_chunks):
            chunks.append({
                "id": self._generate_id(f"{path.name}_{i}"),
                "text": chunk,
                "metadata": {
                    "source": str(path.name),
                    "document_type": "pdf",
                    "chunk_index": i,
                    "total_chunks": len(text_chunks),
                    "page_hint": self._extract_page_number(chunk),
                },
            })

        logger.info("Loaded PDF: %s → %d chunks", path.name, len(chunks))
        return chunks

    # --- Schema Ingestion ---

    def _load_schema(self, path: Path) -> List[Dict]:
        """Load JSON schema and create descriptive chunks."""
        with open(path, "r") as f:
            schema = json.load(f)

        chunks = []

        # Handle different schema formats
        if isinstance(schema, dict):
            # Avro schema
            if schema.get("type") == "record":
                chunks.extend(self._chunk_avro_schema(schema, path.name))
            # JSON Schema
            elif "properties" in schema:
                chunks.extend(self._chunk_json_schema(schema, path.name))
            # Generic dict
            else:
                chunks.extend(self._chunk_dict_schema(schema, path.name))
        elif isinstance(schema, list):
            # Array of table definitions
            for table in schema:
                if isinstance(table, dict):
                    chunks.extend(self._chunk_dict_schema(table, path.name))

        logger.info("Loaded schema: %s → %d chunks", path.name, len(chunks))
        return chunks

    def _chunk_avro_schema(self, schema: Dict, source: str) -> List[Dict]:
        """Convert Avro schema to descriptive text chunks."""
        chunks = []
        table_name = schema.get("name", "unknown")
        doc = schema.get("doc", "")
        fields = schema.get("fields", [])

        # Full schema description
        field_descriptions = []
        for f in fields:
            name = f.get("name", "")
            ftype = f.get("type", "unknown")
            fdoc = f.get("doc", "")
            field_descriptions.append(f"- {name} ({ftype}): {fdoc}")

        schema_text = (
            f"Table: {table_name}\n"
            f"Description: {doc}\n\n"
            f"Columns:\n" + "\n".join(field_descriptions)
        )

        chunks.append({
            "id": self._generate_id(f"schema_{table_name}_full"),
            "text": schema_text,
            "metadata": {
                "source": source,
                "document_type": "schema",
                "table_name": table_name,
                "chunk_type": "full_schema",
            },
        })

        # Per-column chunks for fine-grained retrieval
        for f in fields:
            col_text = (
                f"Column {table_name}.{f['name']} "
                f"(type: {f.get('type', 'unknown')}): "
                f"{f.get('doc', 'No description')}"
            )
            chunks.append({
                "id": self._generate_id(f"schema_{table_name}_{f['name']}"),
                "text": col_text,
                "metadata": {
                    "source": source,
                    "document_type": "schema",
                    "table_name": table_name,
                    "column_name": f["name"],
                    "column_type": str(f.get("type", "")),
                    "chunk_type": "column",
                },
            })

        return chunks

    def _chunk_json_schema(self, schema: Dict, source: str) -> List[Dict]:
        """Convert JSON Schema to chunks."""
        chunks = []
        title = schema.get("title", "unknown")
        desc = schema.get("description", "")
        props = schema.get("properties", {})

        prop_lines = []
        for name, prop in props.items():
            ptype = prop.get("type", "unknown")
            pdesc = prop.get("description", "")
            prop_lines.append(f"- {name} ({ptype}): {pdesc}")

        text = f"Schema: {title}\n{desc}\n\nFields:\n" + "\n".join(prop_lines)

        chunks.append({
            "id": self._generate_id(f"jsonschema_{title}"),
            "text": text,
            "metadata": {
                "source": source,
                "document_type": "schema",
                "schema_name": title,
                "chunk_type": "full_schema",
            },
        })

        return chunks

    def _chunk_dict_schema(self, schema: Dict, source: str) -> List[Dict]:
        """Convert generic dict schema to a descriptive chunk."""
        text = json.dumps(schema, indent=2, default=str)

        # Truncate if too large
        if len(text) > 5000:
            text = text[:5000] + "\n... (truncated)"

        name = schema.get("name", schema.get("table", "unknown"))
        return [{
            "id": self._generate_id(f"dictschema_{name}"),
            "text": text,
            "metadata": {
                "source": source,
                "document_type": "schema",
                "chunk_type": "dict_schema",
            },
        }]

    # --- Text Ingestion ---

    def _load_text(
        self, path: Path, chunk_size: int, chunk_overlap: int
    ) -> List[Dict]:
        """Load and chunk a text file."""
        text = path.read_text(encoding="utf-8")
        text_chunks = self._chunk_text(text, chunk_size, chunk_overlap)

        chunks = []
        for i, chunk in enumerate(text_chunks):
            chunks.append({
                "id": self._generate_id(f"{path.name}_{i}"),
                "text": chunk,
                "metadata": {
                    "source": str(path.name),
                    "document_type": path.suffix.lstrip("."),
                    "chunk_index": i,
                    "total_chunks": len(text_chunks),
                },
            })

        logger.info("Loaded text: %s → %d chunks", path.name, len(chunks))
        return chunks

    # --- Chunking Utilities ---

    def _chunk_text(
        self, text: str, chunk_size: int, chunk_overlap: int
    ) -> List[str]:
        """
        Split text into overlapping chunks.
        Respects paragraph and sentence boundaries.
        """
        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end < len(text):
                # Try to break at paragraph boundary
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break + 2
                else:
                    # Try sentence boundary
                    sentence_break = max(
                        text.rfind(". ", start, end),
                        text.rfind("? ", start, end),
                        text.rfind("! ", start, end),
                    )
                    if sentence_break > start + chunk_size // 3:
                        end = sentence_break + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap
            if start >= len(text):
                break

        return chunks

    def _generate_id(self, content: str) -> str:
        """Generate deterministic ID from content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_page_number(self, text: str) -> Optional[int]:
        """Extract page number hint from chunk text."""
        match = re.search(r"--- Page (\d+) ---", text)
        return int(match.group(1)) if match else None
