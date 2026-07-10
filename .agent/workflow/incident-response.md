# Incident Response Runbook

## Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| SEV1 | Platform down, data loss risk | 15 min | CTO + VP Eng |
| SEV2 | Major feature degraded | 30 min | On-call lead |
| SEV3 | Minor feature issue | 4 hours | Team lead |
| SEV4 | Cosmetic / low impact | Next sprint | Ticket only |

## SEV1: Flink Pipeline Down (Checkpoint Failing >5min)

1. **Acknowledge** PagerDuty alert
2. **Assess**: Check Flink Web UI for job status
   ```bash
   kubectl port-forward svc/flink-jobmanager 8081:8081 -n aion-ingestion
   ```
3. **Check Kafka**: Is source topic receiving data?
   ```bash
   kexec kafka-0 -- kafka-console-consumer --bootstrap-server localhost:9092 --topic legacy.orders --max-messages 1
   ```
4. **Check state backend**: Is S3 accessible?
   ```bash
   kexec flink-taskmanager-0 -- aws s3 ls s3://aion-flink-state/checkpoints/
   ```
5. **Try restart**: Cancel and resubmit the Flink job
6. **If S3 is the issue**: Check IRSA role, S3 bucket policy
7. **If Kafka is the issue**: Check MSK broker health, network ACLs
8. **Escalate** if not resolved in 30 minutes

## SEV2: Copilot API Unavailable

1. Check pod health:
   ```bash
   kubectl get pods -n aion-copilot -l app=aion-copilot
   kubectl logs deployment/copilot -n aion-copilot --tail=50
   ```
2. Check dependencies: Qdrant, Trino, LLM API
3. If LLM API is down, Copilot should return cached responses
4. If Qdrant is down, check Redis connectivity
5. Scale up if resource exhaustion:
   ```bash
   kubectl scale deployment/copilot --replicas=5 -n aion-copilot
   ```

## SEV2: Trino Query Engine Slow

1. Check worker count and resource usage
2. Look for long-running queries:
   ```sql
   SELECT query_id, state, query, started FROM system.runtime.queries
   WHERE state = 'RUNNING' ORDER BY created DESC;
   ```
3. Kill stuck queries if needed
4. Scale Trino workers if consistently slow

## SEV3: Iceberg Table Write Conflicts

1. Check for concurrent writers (optimistic concurrency)
2. Look at recent snapshots:
   ```sql
   SELECT * FROM awsdatacatalog.aion."table_name$snapshots"
   ORDER BY committed_at DESC LIMIT 5;
   ```
3. Ensure only one writer per partition at a time
4. Check if manifest merge is enabled in table properties

## Post-Incident

1. Write incident report within 24 hours
2. Update runbook if new failure mode discovered
3. Add monitoring alert if gap identified
4. Schedule blameless post-mortem for SEV1/SEV2
