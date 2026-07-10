"""
AION Copilot — FastAPI Application
===================================
RAG-powered executive AI assistant with LangChain, Qdrant, and Trino.

Endpoints:
  POST /chat                    — Main RAG chat endpoint
  POST /chat/stream             — Streaming RAG chat
  POST /ingest/documents        — Ingest PDFs and schemas into Qdrant
  GET  /health                  — Health check
  GET  /collections             — List vector collections
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.rag.pipeline import RAGPipeline
from app.guardrails.safety import SafetyGuardrail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aion-copilot")


# =============================================================================
# Lifespan — initialize shared resources
# =============================================================================

rag_pipeline: RAGPipeline = None
guardrail: SafetyGuardrail = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_pipeline, guardrail
    logger.info("Initializing AION Copilot...")

    guardrail = SafetyGuardrail()
    rag_pipeline = RAGPipeline(guardrail=guardrail)

    logger.info("AION Copilot ready")
    yield

    logger.info("Shutting down AION Copilot...")
    if rag_pipeline:
        await rag_pipeline.close()


app = FastAPI(
    title="AION Copilot",
    description="AI-powered executive assistant for AION platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request / Response Models
# =============================================================================

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="User question in natural language")
    user_id: str = Field(default="anonymous", description="Authenticated user ID")
    conversation_id: str = Field(default=None, description="Conversation thread ID")
    max_results: int = Field(default=50, ge=1, le=500,
                             description="Max SQL rows returned")
    model_preference: str = Field(default=None,
                                  description="Preferred LLM: 'claude' or 'openai'")


class ChatResponse(BaseModel):
    answer: str
    sql_query: str = None
    sql_results: list = None
    retrieved_context: list = None
    guardrail_flags: list = []
    model_used: str = None
    tokens_used: int = 0
    latency_ms: float = 0


class IngestRequest(BaseModel):
    documents: list  # List of file paths or URLs
    collection_name: str = "aion_business_context"
    chunk_size: int = 1000
    chunk_overlap: int = 200


class IngestResponse(BaseModel):
    documents_processed: int
    chunks_created: int
    collection_name: str


# =============================================================================
# Endpoints
# =============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main RAG endpoint:
      1. Guardrail check (SQL injection, PII)
      2. Vector search for business context
      3. LLM generates Spark SQL from context
      4. Execute SQL against Trino
      5. LLM generates executive summary
    """
    result = await rag_pipeline.answer(
        question=request.question,
        user_id=request.user_id,
        max_results=request.max_results,
        model_preference=request.model_preference,
    )
    return ChatResponse(**result)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming variant — returns Server-Sent Events."""
    from fastapi.responses import StreamingResponse

    async def event_generator():
        async for chunk in rag_pipeline.answer_stream(
            question=request.question,
            user_id=request.user_id,
            max_results=request.max_results,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/ingest/documents", response_model=IngestResponse)
async def ingest_documents(request: IngestRequest):
    """Ingest PDFs and table schemas into Qdrant."""
    from app.ingestion.document_loader import DocumentIngester

    ingester = DocumentIngester()
    result = await ingester.ingest(
        documents=request.documents,
        collection_name=request.collection_name,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    return IngestResponse(**result)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "aion-copilot",
        "version": "1.0.0",
    }


@app.get("/collections")
async def list_collections():
    """List Qdrant collections."""
    from app.rag.vector_store import VectorStore

    vs = VectorStore()
    collections = vs.list_collections()
    await vs.close()
    return {"collections": collections}
