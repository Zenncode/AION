# AION System Architecture

## High-Level Data Flow

```
Sources → Ingestion → Storage → Serving → Consumption
  │           │           │          │          │
  │     CDC (Debezium)  Iceberg   Trino     Frontend
  │     Streaming       Gold      Query     Copilot
  │     (Kafka→Flink)   Tables    Engine    Dashboards
  │           │           │          │          │
  │     Batch (Spark)  Feature    MLflow     Charts
  │     Bronze→Silver   Store     Triton     Reports
  │                     (Feast)   Serving
  │
  └── PostgreSQL, APIs, IoT, Files, S3
```

## Subsystem Map

| Subsystem | Directory | Purpose | Key Tech |
|-----------|-----------|---------|----------|
| Infrastructure | `terraform/` | AWS VPC, EKS, RDS, MSK | Terraform, AWS |
| Ingestion | `ingestion/` | CDC + streaming + batch ETL | Debezium, Flink, Spark |
| Storage | `storage/` | Iceberg lakehouse + query engine | Iceberg, Trino, PyIceberg |
| MLOps | `mlops/` | Feature store + training + serving | Feast, Kubeflow, MLflow, Triton |
| Copilot | `copilot/` | RAG-powered AI assistant | LangChain, Qdrant, FastAPI |
| Frontend | `src/` + `frontend/` | Executive dashboard + chat UI | React, Apollo, AG-Grid |
| CI/CD | `cicd/` | GitOps + pipelines + alerts | ArgoCD, Jenkins, Kustomize |

## Data Layers (Medallion Architecture)

```
Bronze (Raw)     → S3 aion-bronze-raw       → JSON files, CDC snapshots
Silver (Cleansed) → S3 aion-silver-lakehouse → Iceberg, Parquet+zstd
Gold (Business)  → S3 aion-gold-lakehouse   → Iceberg, aggregated tables
Platinum (ML)    → Feast Feature Store       → Online + offline serving
```

## Service Communication

```
Frontend ──GraphQL──→ API Gateway ──→ Backend services
         ──HTTP────→ Copilot (FastAPI) ──→ Qdrant + Trino + LLM APIs
         ──WebSocket→ Real-time KPIs (Flink → Kafka → Subscription)

Ingestion:
  PostgreSQL ──CDC──→ Debezium ──→ Kafka [legacy.orders]
  Kafka [legacy.orders] ──→ Flink ──→ Kafka [aggregated.sales]
  S3 Bronze ──→ Spark ──→ S3 Silver (Iceberg)

ML:
  Gold Tables ──→ Feast Feature Store ──→ Redis (online)
  Features ──→ Kubeflow Pipeline ──→ MLflow Registry ──→ Triton
```

## AWS Resource Topology

```
VPC 10.0.0.0/16 (eu-west-1)
├── Public Subnets (3 AZs)
│   ├── NAT Gateway
│   └── ALB
├── Private Subnets (3 AZs)
│   ├── EKS Cluster (1.29)
│   │   ├── System nodes (On-Demand)
│   │   └── Worker nodes (Spot)
│   ├── RDS Aurora PostgreSQL (Multi-AZ)
│   └── MSK Kafka (3 brokers)
└── S3 Buckets
    ├── aion-terraform-state
    ├── aion-bronze-raw
    ├── aion-silver-lakehouse
    ├── aion-gold-lakehouse
    ├── aion-mlflow-artifacts
    ├── aion-flink-state
    ├── aion-feast-registry
    └── aion-models
```
