"""
AION Copilot — RAG Pipeline
==============================
Orchestrates the full query → context → SQL → answer flow.
"""

import json
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.config import settings
from app.rag.vector_store import VectorStore
from app.rag.embeddings import EmbeddingService
from app.guardrails.safety import SafetyGuardrail
from app.llm.client import LLMClient
from app.rag.prompts import SYSTEM_PROMPT, SQL_GENERATION_PROMPT, SUMMARY_PROMPT

logger = logging.getLogger("aion-copilot.pipeline")


class RAGPipeline:
    """End-to-end RAG pipeline: question → retrieval → SQL → summary."""

    def __init__(self, guardrail: SafetyGuardrail):
        self.vector_store = VectorStore()
        self.embeddings = EmbeddingService()
        self.guardrail = guardrail
        self.llm = LLMClient()

    async def close(self):
        await self.vector_store.close()

    async def answer(
        self,
        question: str,
        user_id: str = "anonymous",
        max_results: int = 50,
        model_preference: str = None,
    ) -> Dict[str, Any]:
        """Full RAG pipeline — single-shot (non-streaming)."""
        start = time.time()
        guardrail_flags = []

        # --- Step 0: Guardrail check ---
        is_safe, flags = self.guardrail.check(question)
        guardrail_flags.extend(flags)

        if not is_safe:
            return {
                "answer": (
                    "I'm sorry, but I cannot process this request. "
                    "The query contains content that violates our safety policies "
                    "(SQL injection patterns or PII detection). "
                    "Please rephrase your question."
                ),
                "sql_query": None,
                "sql_results": None,
                "retrieved_context": None,
                "guardrail_flags": guardrail_flags,
                "model_used": None,
                "tokens_used": 0,
                "latency_ms": (time.time() - start) * 1000,
            }

        # --- Step 1: Retrieve business context ---
        context_docs = self._retrieve_context(question)
        context_text = self._format_context(context_docs)

        # --- Step 2: Generate Spark SQL ---
        sql_query = await self._generate_sql(
            question=question,
            context=context_text,
            model_preference=model_preference,
        )

        # --- Step 3: Execute SQL against Trino ---
        sql_results = []
        sql_error = None
        if sql_query:
            sql_results, sql_error = await self._execute_sql(sql_query, max_results)

        # --- Step 4: Generate executive summary ---
        model_used = model_preference or settings.default_llm
        answer_text, tokens_used = await self._generate_summary(
            question=question,
            context=context_text,
            sql_query=sql_query,
            sql_results=sql_results,
            sql_error=sql_error,
            model_preference=model_preference,
        )

        latency_ms = (time.time() - start) * 1000
        logger.info(
            "Pipeline complete: user=%s, latency=%.0fms, tokens=%d",
            user_id, latency_ms, tokens_used,
        )

        return {
            "answer": answer_text,
            "sql_query": sql_query,
            "sql_results": sql_results[:max_results] if sql_results else None,
            "retrieved_context": [d["text"][:500] for d in context_docs[:5]],
            "guardrail_flags": guardrail_flags,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "latency_ms": round(latency_ms, 1),
        }

    async def answer_stream(
        self,
        question: str,
        user_id: str = "anonymous",
        max_results: int = 50,
    ) -> AsyncGenerator[str, None]:
        """Streaming variant — yields partial answers."""
        is_safe, flags = self.guardrail.check(question)
        if not is_safe:
            yield json.dumps({"type": "guardrail_block", "flags": flags})
            return

        # Retrieve context
        context_docs = self._retrieve_context(question)
        context_text = self._format_context(context_docs)
        yield json.dumps({"type": "context_retrieved", "count": len(context_docs)})

        # Generate SQL
        sql_query = await self._generate_sql(question, context_text)
        yield json.dumps({"type": "sql_generated", "sql": sql_query})

        # Execute SQL
        sql_results, sql_error = [], None
        if sql_query:
            sql_results, sql_error = await self._execute_sql(sql_query, max_results)
            yield json.dumps({"type": "sql_executed", "row_count": len(sql_results)})

        # Stream summary
        async for chunk in self._stream_summary(
            question, context_text, sql_query, sql_results, sql_error
        ):
            yield json.dumps({"type": "answer_chunk", "content": chunk})

        yield json.dumps({"type": "done"})

    # --- Internal methods ---

    def _retrieve_context(self, question: str) -> List[Dict]:
        """Vector search for relevant business context."""
        query_embedding = self.embeddings.embed_query(question)

        results = self.vector_store.search(
            collection_name=settings.qdrant_collection,
            query_embedding=query_embedding,
            top_k=settings.rag_top_k,
        )

        logger.info("Retrieved %d context documents", len(results))
        return results

    def _format_context(self, docs: List[Dict]) -> str:
        """Format retrieved documents into a context block."""
        if not docs:
            return "No relevant business context found."

        parts = []
        total_length = 0

        for doc in docs:
            text = doc["text"].strip()
            source = doc.get("metadata", {}).get("source", "unknown")
            chunk = f"[Source: {source}]\n{text}"
            if total_length + len(chunk) > settings.rag_max_context_length:
                break
            parts.append(chunk)
            total_length += len(chunk)

        return "\n\n---\n\n".join(parts)

    async def _generate_sql(
        self,
        question: str,
        context: str,
        model_preference: str = None,
    ) -> Optional[str]:
        """Use LLM to generate Spark SQL from question + schema context."""
        prompt = SQL_GENERATION_PROMPT.format(
            question=question,
            context=context,
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                model_preference=model_preference,
            )

            # Extract SQL from response (may be wrapped in ```sql blocks)
            sql = self._extract_sql(response)
            if sql:
                logger.info("Generated SQL: %s", sql[:200])
            return sql

        except Exception as e:
            logger.error("SQL generation failed: %s", e)
            return None

    def _extract_sql(self, text: str) -> Optional[str]:
        """Extract SQL query from LLM response."""
        # Try to find SQL in code blocks
        patterns = [
            r"```sql\s*\n(.*?)```",
            r"```\s*\n(.*?)```",
            r"SELECT\s+.*?(?:;|$)",
            r"WITH\s+.*?(?:;|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(1) if match.lastindex else match.group(0)
                sql = sql.strip().rstrip(";")
                # Basic SQL validation
                if any(kw in sql.upper() for kw in ("SELECT", "WITH", "FROM")):
                    return sql

        return None

    async def _execute_sql(
        self,
        sql_query: str,
        max_results: int = 50,
    ) -> tuple:
        """Execute SQL against Trino and return results."""
        from app.rag.trino_client import TrinoExecutor

        executor = TrinoExecutor()
        try:
            results = await executor.execute(sql_query, max_rows=max_results)
            return results, None
        except Exception as e:
            logger.error("SQL execution failed: %s", e)
            return [], str(e)
        finally:
            await executor.close()

    async def _generate_summary(
        self,
        question: str,
        context: str,
        sql_query: str,
        sql_results: list,
        sql_error: str,
        model_preference: str = None,
    ) -> tuple:
        """Generate executive-level summary from SQL results + context."""
        # Format results for LLM
        if sql_results:
            results_text = json.dumps(sql_results[:20], indent=2, default=str)
            if len(sql_results) > 20:
                results_text += f"\n... ({len(sql_results)} total rows)"
        elif sql_error:
            results_text = f"SQL Error: {sql_error}"
        else:
            results_text = "No results returned."

        prompt = SUMMARY_PROMPT.format(
            question=question,
            context=context[:2000],
            sql_query=sql_query or "N/A",
            sql_results=results_text,
        )

        response, tokens = await self.llm.generate_with_usage(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model_preference=model_preference,
        )

        return response, tokens

    async def _stream_summary(
        self,
        question: str,
        context: str,
        sql_query: str,
        sql_results: list,
        sql_error: str,
    ) -> AsyncGenerator[str, None]:
        """Stream executive summary token by token."""
        results_text = json.dumps(sql_results[:20], indent=2, default=str) if sql_results else "No results."

        prompt = SUMMARY_PROMPT.format(
            question=question,
            context=context[:2000],
            sql_query=sql_query or "N/A",
            sql_results=results_text,
        )

        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            system=SYSTEM_PROMPT,
        ):
            yield chunk
