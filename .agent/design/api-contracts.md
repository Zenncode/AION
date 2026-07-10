# API Contracts

## Copilot REST API

### POST /chat

Request:
```json
{
  "question": "Why did sales drop in the West region yesterday?",
  "user_id": "exec-001",
  "max_results": 50,
  "model_preference": "claude"
}
```

Response:
```json
{
  "answer": "Sales in the West region declined 12.3% compared to the previous day...",
  "sql_query": "SELECT event_date, SUM(net_amount) AS revenue FROM awsdatacatalog.gold.financial_transactions WHERE region = 'west' AND event_date >= DATE '2024-01-14' GROUP BY event_date ORDER BY event_date",
  "sql_results": [
    {"event_date": "2024-01-14", "revenue": 142350.00},
    {"event_date": "2024-01-15", "revenue": 124890.00}
  ],
  "retrieved_context": ["[Source: policy.pdf] Revenue recognition policy..."],
  "guardrail_flags": [],
  "model_used": "claude",
  "tokens_used": 1847,
  "latency_ms": 3420.0
}
```

### POST /chat/stream

Same request. Returns Server-Sent Events:
```
data: {"type": "context_retrieved", "count": 8}
data: {"type": "sql_generated", "sql": "SELECT ..."}
data: {"type": "sql_executed", "row_count": 30}
data: {"type": "answer_chunk", "content": "Sales "}
data: {"type": "answer_chunk", "content": "in the "}
data: {"type": "done"}
```

---

## GraphQL Schema (Key Types)

```graphql
type Query {
  revenueMetrics(dateRange: DateRangeInput!): RevenueMetrics
  activeUsers(dateRange: DateRangeInput!): ActiveUsersMetrics
  inventoryMetrics(dateRange: DateRangeInput!): InventoryMetrics
  executiveKPIs: ExecutiveKPIs
  financialTransactions(
    startRow: Int!, endRow: Int!
    sortModel: [SortInput!], filterModel: FilterInput
  ): TransactionConnection
  customer360(...): CustomerConnection
  inventorySnapshot(...): InventoryConnection
}

type Subscription {
  kpiUpdated: KPIData
  revenueStream: RevenueEvent
}

type Mutation {
  copilotChat(input: CopilotInput!): CopilotResponse
}
```

---

## Kafka Topics

| Topic | Partitions | Retention | Producers | Consumers |
|-------|-----------|-----------|-----------|-----------|
| `legacy.orders` | 3 | 7 days | Debezium | Flink |
| `aggregated.sales` | 3 | 30 days | Flink | Copilot (push) |
| `aggregated.sales.dlq` | 1 | 7 days | Flink | Manual review |
| `debezium-configs` | 1 | - | Debezium Connect | Internal |
| `debezium-offsets` | 1 | - | Debezium Connect | Internal |

---

## Feature Store (Feast)

Entity: `customer_id` (BIGINT)

Online features (Redis):
- `click_rate_7d` (Float32)
- `avg_transaction_value` (Float64)
- `total_orders_30d` (Int64)
- `rfm_composite_score` (Float32)
- `churn_risk_score` (Float32)

Offline features (Iceberg via Glue):
- All of the above plus `gdpr_consent`, `segment`, `tier`
