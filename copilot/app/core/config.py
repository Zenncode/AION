"""
AION Copilot — Configuration
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # --- Qdrant ---
    qdrant_host: str = os.getenv("QDRANT_HOST", "qdrant.aion-mlops.svc.cluster.local")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "aion_business_context")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    qdrant_url: str = os.getenv("QDRANT_URL", "")

    # --- Embeddings ---
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    # --- LLM ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    default_llm: str = os.getenv("DEFAULT_LLM", "claude")  # "claude" or "openai"
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # --- Trino ---
    trino_host: str = os.getenv("TRINO_HOST", "trino-coordinator.aion-analytics.svc.cluster.local")
    trino_port: int = int(os.getenv("TRINO_PORT", "8080"))
    trino_user: str = os.getenv("TRINO_USER", "aion-copilot")
    trino_catalog: str = os.getenv("TRINO_CATALOG", "awsdatacatalog")
    trino_schema: str = os.getenv("TRINO_SCHEMA", "gold")
    trino_source: str = os.getenv("TRINO_SOURCE", "aion-copilot")

    # --- RAG ---
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "10"))
    rag_score_threshold: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.65"))
    rag_max_context_length: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "8000"))

    # --- Guardrails ---
    guardrail_enabled: bool = os.getenv("GUARDRAIL_ENABLED", "true").lower() == "true"
    pii_detection_enabled: bool = os.getenv("PII_DETECTION_ENABLED", "true").lower() == "true"
    sql_injection_block: bool = os.getenv("SQL_INJECTION_BLOCK", "true").lower() == "true"

    # --- Iceberg ---
    iceberg_warehouse: str = os.getenv("ICEBERG_WAREHOUSE", "s3://aion-silver-lakehouse")
    schema_registry_path: str = os.getenv("SCHEMA_REGISTRY_PATH", "")


settings = Settings()
