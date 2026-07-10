# AION — Complete Run Guide

Single reference for standing up the entire AION platform locally and on AWS.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [Infrastructure (Terraform)](#3-infrastructure-terraform)
4. [Local Development (Docker Compose)](#4-local-development-docker-compose)
5. [Kubernetes Deployment](#5-kubernetes-deployment)
6. [Storage Layer](#6-storage-layer)
7. [Ingestion Pipeline](#7-ingestion-pipeline)
8. [MLOps Pipeline](#8-mlops-pipeline)
9. [AI Copilot](#9-ai-copilot)
10. [Frontend](#10-frontend)
11. [CI/CD Pipeline](#11-cicd-pipeline)
12. [Monitoring](#12-monitoring)
13. [Environment Matrix](#13-environment-matrix)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

### CLI Tools

```bash
# Required
terraform >= 1.5.0
kubectl >= 1.29
docker >= 24.0
helm >= 3.14
aws-cli >= 2.15
kustomize >= 5.3.0

# For local dev
node >= 20.x
python >= 3.11
java >= 17 (Maven for Flink)
```

### AWS Account Setup

```bash
# Configure credentials
aws configure --profile aion
# Or export:
export AWS_PROFILE=aion
export AWS_REGION=eu-west-1

# Create S3 bucket for Terraform state
aws s3 mb s3://aion-terraform-state --region eu-west-1
aws dynamodb create-table \
  --table-name terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1
```

### API Keys (Copilot)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# OR
export OPENAI_API_KEY=sk-...
```

---

## 2. Project Structure

```
AION/
├── terraform/                  # AWS infrastructure (EKS, RDS, MSK, VPC)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── ingestion/                  # Data ingestion layer
│   ├── docker/                 # Local dev stack (Compose)
│   ├── flink/                  # Flink job (Java, Dockerfile)
│   ├── spark/                  # PySpark Bronze→Silver
│   ├── k8s/                    # K8s manifests (base + overlays)
│   └── airflow/                # Airflow DAGs
│
├── storage/                    # Storage layer
│   ├── iceberg/sql/            # Gold table DDLs, materialized views
│   ├── trino/                  # Trino ConfigMap + deployment
│   └── pyiceberg/              # Iceberg ingestion script
│
├── mlops/                      # ML operations
│   ├── feast/                  # Feature store (definitions + K8s)
│   └── kubeflow/               # Pipeline DSL + Triton + MLflow
│
├── copilot/                    # AI Copilot (FastAPI + LangChain)
│   ├── app/                    # Python application
│   └── k8s/                    # K8s deployment
│
├── src/                        # Frontend (React + TypeScript)
│   ├── components/             # Dashboard, Copilot, DataTable
│   ├── graphql/                # Apollo queries/mutations
│   └── auth/                   # Keycloak integration
│
├── cicd/                       # CI/CD
│   ├── argocd/                 # ArgoCD Application + Project
│   ├── jenkins/                # Jenkinsfile
│   ├── kustomize/              # Env overlays (dev/staging/prod)
│   └── monitoring/             # PrometheusRule alerts
│
├── .agent/context.md           # Agent context for AI assistants
├── CONTEXT.md                  # Project overview
├── RUN.md                      # This file
└── README.md
```

**Total: ~80 files across 9 subsystems**

---

## 3. Infrastructure (Terraform)

### Deploy

```bash
cd terraform

# Initialize
terraform init

# Plan (review what will be created)
terraform plan \
  -var="environment=development" \
  -var="database_master_password=<CHOOSE_A_PASSWORD>" \
  -out=tfplan

# Apply
terraform apply tfplan

# Save outputs
terraform output -json > ../terraform-outputs.json
```

### What Gets Created

| Resource | Default Configuration |
|---|---|
| VPC | 10.0.0.0/16, 3 public + 3 private subnets, NAT Gateway |
| EKS Cluster | Kubernetes 1.29, IRSA enabled, 4 addons |
| System Node Group | 2-4 On-Demand m6i.xlarge, CriticalAddonsOnly taint |
| Worker Node Group | 2-10 Spot (m6i/m5/c6i mixed) |
| Aurora PostgreSQL | 15.4 Multi-AZ, encrypted, performance insights |
| MSK Kafka | 3.5.1, 3 brokers on kafka.m5.large, TLS + KMS |
| IRSA Roles | 6 roles (VPC-CNI, EBS-CSI, MSK, S3, RDS, generic) |

### Configure kubectl

```bash
aws eks update-kubeconfig \
  --name aion-development-eks \
  --region eu-west-1

kubectl get nodes
kubectl get pods -A
```

---

## 4. Local Development (Docker Compose)

```bash
cd ingestion/docker

# Start everything
docker compose up -d

# Verify
docker compose ps

# Check Kafka topics
docker exec aion-kafka kafka-topics \
  --bootstrap-server localhost:9092 --list

# Register CDC connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium-connector.json

# Read CDC events from legacy.orders
docker exec aion-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic legacy.orders \
  --from-beginning --max-messages 5

# Open Kafka UI
open http://localhost:9090

# Open Flink UI
open http://localhost:8081

# Tear down
docker compose down -v
```

### Services Started

| Service | Port | Purpose |
|---|---|---|
| legacy-postgres | 5432 | Mock legacy database with CDC |
| debezium | 8083 | CDC connector REST API |
| kafka | 29092 (host) | Event broker |
| flink-jobmanager | 8081 | Flink Web UI |
| spark-master | 8082 | Spark Web UI |
| schema-registry | 8084 | Schema management |
| kafka-ui | 9090 | Topic/consumer debugging |

---

## 5. Kubernetes Deployment

### Dev Environment

```bash
# Ingestion layer
kubectl apply -k ingestion/k8s/overlays/dev/

# Verify
kubectl get pods -n aion-ingestion-dev
kubectl logs -f deployment/flink-jobmanager -n aion-ingestion-dev

# Copilot
kubectl apply -f copilot/k8s/copilot-deployment.yaml -n aion-copilot

# Trino
kubectl apply -f storage/trino/trino-deployment.yaml -n aion-analytics

# Feast Serving + Redis
kubectl apply -f mlops/feast/k8s/feast-online-serving.yaml -n aion-mlops

# MLflow + Triton
kubectl apply -f mlops/kubeflow/k8s/mlflow-tracking.yaml -n aion-mlops
kubectl apply -f mlops/kubeflow/k8s/triton-deployment.yaml -n aion-inference
```

### Production (via Kustomize)

```bash
# All services at once
kubectl apply -k cicd/kustomize/envs/production/

# Or via ArgoCD
kubectl apply -f cicd/argocd/application.yaml -n argocd
```

---

## 6. Storage Layer

### Gold Tables

```bash
# Connect to Trino
kubectl exec -it trino-coordinator-<pod> -n aion-analytics -- trino

# Run DDLs
# (paste contents of storage/iceberg/sql/001_create_gold_tables.sql)

# Verify tables
SELECT table_name FROM awsdatacatalog.information_schema.tables
WHERE table_schema = 'gold';
```

### Materialized View

```bash
# (paste contents of storage/iceberg/sql/002_materialized_views.sql)

# Refresh from Spark
spark-submit --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3 \
  --conf spark.sql.catalog.s3catalog=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.s3catalog.type=hadoop \
  --conf spark.sql.catalog.s3catalog.warehouse=s3://aion-silver-lakehouse \
  -e "INSERT OVERWRITE INTO s3catalog.aion.dashboard_executive_kpi_snapshot
      SELECT * FROM s3catalog.gold.dashboard_executive_kpi"
```

### PyIceberg Ingestion

```bash
cd storage/pyiceberg
pip install -r requirements.txt

python ingest_gold_tables.py \
  --table customer_360 \
  --input s3://aion-bronze-raw/ml/customers.parquet \
  --event-date 2024-01-15

python ingest_gold_tables.py \
  --table financial_transactions \
  --input s3://aion-bronze-raw/ml/transactions.json \
  --dry-run
```

---

## 7. Ingestion Pipeline

### Flink Job

```bash
cd ingestion/flink

# Build
docker build -t aion-flink-jobmanager:latest .

# Deploy to K8s
kubectl apply -f ../k8s/base/flink.yaml -n aion-ingestion

# Submit job via Flink CLI
kubectl exec -it deployment/flink-jobmanager -n aion-ingestion -- \
  flink run -d /opt/flink/usrlib/aion-sales-aggregator.jar
```

### Spark Pipeline

```bash
cd ingestion/spark/jobs

# Install deps
pip install -r requirements.txt

# Run locally
python bronze_to_silver.py

# Submit to Spark cluster
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3 \
  --conf spark.sql.catalog.s3catalog=org.apache.iceberg.spark.SparkCatalog \
  bronze_to_silver.py
```

### Airflow DAG

```bash
# Copy DAG to Airflow
cp ingestion/airflow/dags/bronze_to_silver_dag.py \
  /opt/airflow/dags/

# Or in K8s
kubectl cp ingestion/airflow/dags/bronze_to_silver_dag.py \
  airflow-scheduler-<pod>:/opt/airflow/dags/
```

---

## 8. MLOps Pipeline

### Feast Feature Store

```bash
cd mlops/feast/feature_repo

# Local dev
pip install feast
feast apply          # Register features
feast materialize    # Push to Redis

# Verify
feast feature-views list
feast entity list
```

### Kubeflow Pipeline

```bash
cd mlops/kubeflow/pipelines

# Compile
pip install kfp
python churn_prediction_pipeline.py --compile
# Outputs: churn_prediction_pipeline.yaml

# Upload to Kubeflow
python churn_prediction_pipeline.py --upload
```

### Triton Deployment

```bash
# Convert model to ONNX, create repo, upload to S3
# (handled automatically by the pipeline's deploy_to_triton component)

# Verify
kubectl exec -it triton-inference-server-<pod> -n aion-inference -- \
  curl -s http://localhost:8000/v2/health/ready
```

---

## 9. AI Copilot

### Run Locally

```bash
cd copilot

pip install -r requirements.txt

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export QDRANT_HOST=localhost
export TRINO_HOST=localhost

# Start
uvicorn app.main:app --reload --port 8000

# Test
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did sales drop in the West region yesterday?"}'
```

### Ingest Documents

```bash
curl -X POST http://localhost:8000/ingest/documents \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      "/path/to/policy.pdf",
      "/path/to/schema.json"
    ],
    "collection_name": "aion_business_context"
  }'
```

### Deploy to K8s

```bash
kubectl apply -f copilot/k8s/copilot-deployment.yaml

# Test endpoint
kubectl port-forward svc/aion-copilot 8000:8000 -n aion-copilot
```

---

## 10. Frontend

### Local Development

```bash
cd frontend

npm install

# Start dev server (proxies API calls to K8s)
npm run dev
# Opens at http://localhost:3000
```

### Build & Deploy

```bash
# Production build
npm run build
# Outputs to frontend/dist/

# Docker build
docker build -t aion/frontend:latest -f Dockerfile frontend/
```

### Environment Variables

Create `frontend/.env.local`:

```
VITE_KEYCLOAK_URL=https://auth.aion.internal
VITE_KEYCLOAK_REALM=aion
VITE_KEYCLOAK_CLIENT_ID=aion-frontend
VITE_GRAPHQL_URL=http://localhost:4000/graphql
VITE_GRAPHQL_WS_URL=ws://localhost:4000/graphql
```

---

## 11. CI/CD Pipeline

### Jenkins

1. Add `Jenkinsfile` to repo root
2. Configure credentials: `aion-aws-credentials`, `git-credentials`, `argocd-token`
3. Pipeline runs on push to `main`/`develop`:
   - Lint → Build Docker images → Push to ECR → Update Kustomize tags → Commit to GitOps repo → ArgoCD auto-syncs

### ArgoCD

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Apply AION projects + applications
kubectl apply -f cicd/argocd/project.yaml
kubectl apply -f cicd/argocd/application.yaml

# Login
argocd login <ARGOCD_URL> --username admin --password <password>
```

---

## 12. Monitoring

### Prometheus Rules

```bash
# Apply alerting rules
kubectl apply -f cicd/monitoring/prometheus-rules.yaml

# Verify rules are loaded
kubectl get prometheusrule -n aion-mlops
```

### Key Alerts

| Alert | Trigger | Severity |
|---|---|---|
| FlinkCheckpointFailureCritical | Failed checkpoints for >5 min | Critical → PagerDuty |
| FlinkNoCheckpoints | No checkpoint in 15 min | Critical → PagerDuty |
| FlinkJobDown | Job not reporting metrics | Critical → PagerDuty |
| FlinkBackpressureHigh | Backpressure >80% for 5 min | Warning |
| AIONCopilotDown | API unreachable >2 min | Critical → PagerDuty |
| AIONErrorBudgetBurnHigh | Error rate >14.4x budget | Critical → PagerDuty |
| KafkaConsumerLagHigh | Lag >100K messages | Warning |

### Grafana Dashboards

Pre-built dashboards for each subsystem (import JSON available on request):
- Flink Overview: checkpoint success rate, throughput, backpressure
- Kafka: consumer lag, broker health, topic throughput
- EKS: node capacity, pod restarts, resource utilization
- Copilot: request latency P95, error rate, guardrail blocks

---

## 13. Environment Matrix

| Setting | Development | Staging | Production |
|---|---|---|---|
| EKS Workers | 2-4 Spot | 2-10 Spot | 2-10 Spot |
| NAT Gateways | 1 | 1 | 3 (per-AZ) |
| RDS Instances | 1 | 1 | 2 (Multi-AZ) |
| RDS Backup | 7 days | 7 days | 14 days |
| Kafka Brokers | 1 (local) | 3 (MSK) | 3 (MSK) |
| Flink TaskManagers | 1 | 2 | 4 |
| Spark Workers | 1 | 2 | 4 |
| Trino Workers | 1 | 2 | 3 |
| Copilot Replicas | 1 | 2 | 3 |
| Frontend Replicas | 1 | 2 | 3 |
| Redis Nodes | 1 | 3 | 3 |
| Triton GPUs | 0 | 1 | 2 |
| Logging | DEBUG | INFO | WARN |
| Auto-sync (ArgoCD) | Manual | Auto | Auto |

---

## 14. Troubleshooting

### Flink Job Not Starting

```bash
kubectl logs deployment/flink-jobmanager -n aion-ingestion --tail=100
kubectl logs deployment/flink-taskmanager -n aion-ingestion --tail=100

# Check Kafka connectivity
kubectl exec -it kafka-0 -n aion-data -- \
  kafka-topics --bootstrap-server localhost:9092 --list
```

### Copilot Returning Empty Answers

```bash
# Check Qdrant collection has data
kubectl port-forward svc/qdrant 6333:6333 -n aion-mlops
curl http://localhost:6333/collections/aion_business_context

# Check Trino connectivity
kubectl exec -it trino-coordinator-<pod> -n aion-analytics -- \
  trino --execute "SELECT 1"

# Check LLM API keys
kubectl get secret aion-llm-keys -n aion-copilot -o yaml
```

### Terraform State Lock

```bash
# If apply was interrupted
aws dynamodb delete-item \
  --table-name terraform-lock \
  --key '{"LockID": {"S": "aion-terraform-state/eks/terraform.tfstate"}}' \
  --region eu-west-1
```

### ArgoCD Sync Failed

```bash
argocd app get aion-production
argocd app sync aion-production --force
argocd app wait aion-production --health --timeout 300
```

---

## Quick Start (Everything)

```bash
# 1. Infrastructure
cd terraform && terraform apply -var="database_master_password=CHOOSE_ME"
aws eks update-kubeconfig --name aion-development-eks --region eu-west-1

# 2. Deploy all services
kubectl apply -k cicd/kustomize/envs/dev/

# 3. Build and push images
cd ingestion/flink && docker build -t aion/flink:latest .
cd ../../frontend && npm run build && docker build -t aion/frontend:latest .
cd ../copilot && docker build -t aion/copilot:latest .

# 4. Start Copilot locally
cd copilot && pip install -r requirements.txt && uvicorn app.main:app

# 5. Start Frontend locally
cd frontend && npm install && npm run dev

# 6. Open browser
open http://localhost:3000
```
