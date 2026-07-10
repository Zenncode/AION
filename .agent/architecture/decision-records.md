# Architecture Decision Records

## ADR-001: Apache Iceberg over Delta Lake

**Status:** Accepted
**Date:** 2024-01-15

**Decision:** Use Apache Iceberg as the table format for the lakehouse.

**Rationale:**
- Open standard with multi-engine support (Spark, Trino, Flink, PyIceberg)
- Schema evolution without rewriting data
- Time travel queries for audit/compliance
- Partition evolution without data migration
- Better AWS Glue catalog integration than Delta Lake

**Consequences:**
- Requires Glue Data Catalog or custom catalog
- Slightly less mature ecosystem than Delta Lake (closing fast)

---

## ADR-002: Flink over Spark Streaming

**Status:** Accepted
**Date:** 2024-01-15

**Decision:** Use Apache Flink for real-time stream processing, Spark for batch.

**Rationale:**
- Flink provides true event-time processing with exactly-once semantics
- Native Kafka connector with checkpoint-based recovery
- Better suited for 5-minute tumbling windows with late data handling
- Spark Structured Streaming is micro-batch, not true streaming

**Consequences:**
- Two compute engines to maintain (Flink + Spark)
- Separate Docker images and deployment configs
- Team needs both Java (Flink) and Python (Spark) skills

---

## ADR-003: Qdrant over Pinecone

**Status:** Accepted
**Date:** 2024-02-01

**Decision:** Use Qdrant as the vector database for the Copilot RAG pipeline.

**Rationale:**
- Self-hosted on Kubernetes (no vendor lock-in)
- Lower cost at scale vs Pinecone's per-query pricing
- Filter support for metadata-aware retrieval
- Rust-based performance with Docker image availability

**Consequences:**
- Team manages Qdrant cluster lifecycle
- No managed service SLA — must monitor and scale manually

---

## ADR-004: LangChain as LLM Orchestration

**Status:** Accepted
**Date:** 2024-02-01

**Decision:** Use LangChain for the Copilot's RAG pipeline orchestration.

**Rationale:**
- Unified interface for Claude 3 and GPT-4
- Built-in SQL query chain for text-to-SQL
- Prompt template management
- Active community and frequent updates

**Consequences:**
- LangChain API changes frequently — pin versions
- Abstraction can obscure debugging when things go wrong

---

## ADR-005: Kustomize over Helm

**Status:** Accepted
**Date:** 2024-02-15

**Decision:** Use Kustomize for environment configuration, not Helm.

**Rationale:**
- Native kubectl support (no extra tool)
- Simpler patch model for replica/resource overrides
- ArgoCD has native Kustomize support
- No template rendering complexity

**Consequences:**
- Cannot share complex chart libraries
- Must maintain separate base + overlay files
