# AION Ingestion Layer

Event-driven data ingestion pipeline: CDC from legacy PostgreSQL → Kafka → Flink windowed aggregation + Spark Bronze→Silver medallion.

## Architecture

```
Legacy PostgreSQL ──(CDC)──► Debezium ──► Kafka [legacy.orders]
                                              │
                              ┌────────────────┼────────────────┐
                              ▼                                  ▼
                        Flink Job                        Spark Pipeline
                  (5-min tumbling window)          (Bronze → Silver + Iceberg)
                              │                                  │
                              ▼                                  ▼
                  Kafka [aggregated.sales]            S3 Silver (Parquet)
```

## Quick Start — Local

```bash
cd ingestion/docker
docker compose up -d

# Verify Debezium is running
curl -s http://localhost:8083/connectors | jq .

# Register CDC connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium-connector.json

# Check Kafka topics
docker exec aion-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Read CDC events
docker exec aion-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic legacy.orders \
  --from-beginning --max-messages 5
```

## Kubernetes Deployment

```bash
# Dev
kubectl apply -k k8s/overlays/dev/

# Production
kubectl apply -k k8s/overlays/prod/

# Verify
kubectl get pods -n aion-ingestion
kubectl get pods -n aion-ingestion-dev
```

## Build & Push Flink Job

```bash
cd flink
docker build -t aion-flink-jobmanager:latest .
docker tag aion-flink-jobmanager:latest <ecr-repo>/aion-flink-jobmanager:latest
docker push <ecr-repo>/aion-flink-jobmanager:latest
```

## Spark Job (Airflow)

The `airflow/dags/bronze_to_silver_dag.py` submits the PySpark job via SparkSubmitOperator.
Requires: `apache-airflow-providers-apache-spark` provider installed.
