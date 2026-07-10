"""
AION Copilot — Prompt Templates
=================================
Structured prompts for SQL generation and executive summary.
"""

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are AION Copilot, an expert enterprise data analyst for the AION platform.

Your role:
- Translate natural language business questions into Spark SQL queries
- Analyze query results and produce executive-level summaries
- Always cite specific numbers and data points from results
- Be concise, factual, and actionable
- Never fabricate data — if results are empty or errored, say so

Platform context:
- Data warehouse: Apache Iceberg on S3, queried via Trino
- Catalog: awsdatacatalog
- Schema: gold
- Tables: customer_360, inventory_snapshot, financial_transactions, dashboard_executive_kpi_snapshot
- All tables are partitioned by event_date (DATE type)
- Currency is in EUR unless specified
- Timestamps are UTC

SQL conventions:
- Use Trino SQL syntax (not MySQL or PostgreSQL)
- Always include LIMIT clause
- Use event_date for time filtering (it's a DATE column)
- Table references: awsdatacatalog.gold.<table_name>
- For aggregations, always alias computed columns
- Use CAST() for type conversions
- Prefer window functions over subqueries for rankings"""


# =============================================================================
# SQL Generation Prompt
# =============================================================================

SQL_GENERATION_PROMPT = """Generate a Spark SQL query (Trino-compatible) to answer the user's business question.

## Business Context (from documentation and schemas)

{context}

## User Question

{question}

## Instructions

1. Analyze the question to identify: metrics, filters, time range, grouping
2. Reference the correct table(s) from the context above
3. Use Trino SQL syntax with proper catalog/schema qualification
4. Include appropriate WHERE clauses for the time range
5. Add LIMIT clause (max 500 rows)
6. Alias all computed columns for readability

## Output

Return ONLY the SQL query, no explanation. Use this format:

```sql
SELECT ...
```

If the question cannot be answered with available data, explain why in plain text (no SQL)."""


# =============================================================================
# Summary Prompt
# =============================================================================

SUMMARY_PROMPT = """You are an executive data analyst. Based on the SQL query results and business context,
provide a clear, actionable executive summary.

## Original Question

{question}

## Business Context

{context}

## SQL Query Executed

```sql
{sql_query}
```

## Query Results

```json
{sql_results}
```

## Instructions

1. Start with a direct answer to the question (1-2 sentences)
2. Highlight the most important numbers and trends
3. If the question involves a "why" or "reason", suggest possible causes based on the data
4. Use bullet points for key findings
5. End with a recommended action if applicable
6. Keep the response under 300 words
7. If the query errored or returned no results, explain the limitation clearly

## Executive Summary

Provide your analysis below. Use markdown formatting with **bold** for key numbers."""


# =============================================================================
# Schema Description Prompt (for ingestion)
# =============================================================================

SCHEMA_DESCRIPTION_PROMPT = """Describe this database table for a business analyst audience.

Table: {table_name}
Columns: {columns}
Sample rows: {sample_data}

Provide:
1. A one-sentence purpose description
2. Key business metrics available
3. Common query patterns
4. Relationships to other tables"""


# =============================================================================
# Document Chunk Prompt
# =============================================================================

CHUNK_CONTEXT_PROMPT = """This document fragment is from: {source}
Document type: {doc_type}
Topic: {topic}

Content:
{text}"""
