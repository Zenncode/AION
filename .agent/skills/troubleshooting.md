# Troubleshooting Playbooks

## Flink Job Not Starting

1. Check JobManager logs:
   ```bash
   kubectl logs deployment/flink-jobmanager -n aion-ingestion --tail=100
   ```
2. Verify Kafka connectivity:
   ```bash
   kubectl exec -it kafka-0 -- kafka-topics --bootstrap-server localhost:9092 --list
   ```
3. Check if topic `legacy.orders` exists and has data
4. Verify IRSA role annotation on the Flink service account
5. Check S3 checkpoint bucket permissions

## Copilot Returning Empty Answers

1. Check Qdrant has indexed documents:
   ```bash
   kubectl port-forward svc/qdrant 6333:6333 -n aion-mlops
   curl http://localhost:6333/collections/aion_business_context
   ```
2. Verify LLM API keys are set:
   ```bash
   kubectl get secret aion-llm-keys -n aion-copilot -o jsonpath='{.data}'
   ```
3. Test Trino connectivity from copilot pod:
   ```bash
   kubectl exec -it deployment/copilot -n aion-copilot -- python -c "from trino.dbapi import connect; c=connect(host='trino-coordinator.aion-analytics.svc.cluster.local',port=8080,user='test'); print(c.cursor().execute('SELECT 1').fetchone())"
   ```
4. Check guardrail isn't blocking the query (look for `guardrail_flags` in response)

## ArgoCD Sync Failed

```bash
argocd app get aion-production
argocd app sync aion-production --force
argocd app wait aion-production --health --timeout 300
# If still failing, check resource status:
kubectl get events -n aion-production --sort-by='.lastTimestamp'
```

## Terraform State Lock

```bash
# If apply was interrupted:
aws dynamodb delete-item \
  --table-name terraform-lock \
  --key '{"LockID": {"S": "aion-terraform-state/eks/terraform.tfstate"}}' \
  --region eu-west-1
```

## Kafka Consumer Lag

```bash
# Check lag per consumer group:
kubectl exec -it kafka-0 -- kafka-consumer-groups \
  --bootstrap-server localhost:9092 --describe --group aion-flink-sales-aggregator

# If lag is growing, check Flink backpressure in Web UI:
# http://flink-jobmanager.aion-ingestion.svc.cluster.local:8081
```

## RDS Connection Exhaustion

```bash
# Check current connections:
kubectl exec -it postgresql-0 -- psql -U aion_admin -d aion -c "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections:
kubectl exec -it postgresql-0 -- psql -U aion_admin -d aion -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '10 minutes';"
```

## Iceberg Table Write Failures

1. Check S3 permissions (IRSA role on Spark/Flink service account)
2. Verify Glue catalog access
3. Check for concurrent writers (Iceberg uses optimistic concurrency)
4. Look for long-running snapshots blocking commits:
   ```sql
   SELECT * FROM awsdatacatalog.aion."snapshots$entries" ORDER BY committed_at DESC LIMIT 5;
   ```
