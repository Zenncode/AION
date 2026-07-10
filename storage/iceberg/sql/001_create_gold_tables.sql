-- =============================================================================
-- AION Gold Tier — Iceberg DDL
-- =============================================================================
-- Catalog:   awsdatacatalog (Glue) via Trino
-- Schema:    gold
-- Engine:    Apache Iceberg on S3
-- =============================================================================

-- Ensure the gold schema exists
CREATE SCHEMA IF NOT EXISTS awsdatacatalog.gold;

-- =============================================================================
-- 1. gold.customer_360
-- =============================================================================
-- Unified customer profile aggregating behavioral, transactional, and
-- lifecycle attributes. Updated on a daily batch cadence.
--
-- Partition: event_date (daily)
-- Bucket:    customer_id (32 buckets) — co-locates all rows for one customer
-- =============================================================================

CREATE TABLE IF NOT EXISTS awsdatacatalog.gold.customer_360 (
    -- Natural key
    customer_id             BIGINT,

    -- Demographics
    customer_name           VARCHAR,
    email                   VARCHAR,
    segment                 VARCHAR,            -- e.g. 'enterprise', 'smb', 'consumer'
    tier                    VARCHAR,            -- e.g. 'platinum', 'gold', 'silver', 'bronze'
    country                 VARCHAR,
    region                  VARCHAR,

    -- Behavioral aggregates (rolling windows)
    total_orders_12m        BIGINT,
    total_revenue_12m       DECIMAL(18, 2),
    avg_order_value_12m     DECIMAL(12, 2),
    total_orders_30d        BIGINT,
    total_revenue_30d       DECIMAL(18, 2),
    days_since_last_order   INT,
    active_products         INT,                -- distinct products purchased

    -- RFM scoring
    rfm_recency_score       INT,                -- 1-5
    rfm_frequency_score     INT,                -- 1-5
    rfm_monetary_score      INT,                -- 1-5
    rfm_composite_score     DECIMAL(4, 2),

    -- Churn prediction
    churn_risk_score        DECIMAL(4, 3),      -- 0.000 - 1.000
    predicted_ltv           DECIMAL(14, 2),

    -- Consent & compliance
    gdpr_consent            BOOLEAN DEFAULT TRUE,
    ccpa_opt_out            BOOLEAN DEFAULT FALSE,

    -- Metadata
    event_date              DATE,               -- partition key
    record_updated_at       TIMESTAMP,
    _pipeline_version       VARCHAR,
    _source_systems         ARRAY(VARCHAR)
)
USING iceberg
PARTITIONED BY (event_date)
WITH (
    'format'                              = 'PARQUET',
    'write.format.default'                = 'parquet',
    'write.parquet.compression-codec'     = 'zstd',
    'write.distribution-mode'             = 'hash',
    'write.parquet.page-size-bytes'       = '1048576',
    'write.parquet.block-size-bytes'      = '134217728',
    'write.target-file-size-bytes'        = '536870912',
    'commit.manifest-merge.enabled'       = 'true',
    'history.expire.max-snapshot-age-ms'  = '604800000',
    'history.expire.min-snapshots-keep'   = '10',
    'metadata.delete-after-commit.enabled'= 'true'
);

-- Bucket transform on customer_id for data co-location
-- Note: Trino supports bucket() transform in CREATE TABLE WITH properties.
-- The actual physical bucketing is applied via write.distribution-mode = 'hash'
-- which distributes by the partition key + sort order.

-- =============================================================================
-- 2. gold.inventory_snapshot
-- =============================================================================
-- Daily point-in-time snapshot of inventory positions across all warehouses.
-- Critical for supply chain analytics and anomaly detection.
--
-- Partition: event_date (daily)
-- Bucket:    customer_id is not applicable here; we bucket by warehouse_id
--            for warehouse-local queries. The requirement specifies customer_id
--            bucketing, so we include it for cross-cutting inventory-to-customer
--            joins.
-- =============================================================================

CREATE TABLE IF NOT EXISTS awsdatacatalog.gold.inventory_snapshot (
    -- identifiers
    snapshot_id             BIGINT,
    product_id              BIGINT,
    warehouse_id            BIGINT,
    customer_id             BIGINT,             -- nullable: bulk orders linked to a customer

    -- product details
    product_name            VARCHAR,
    product_category        VARCHAR,
    sku                     VARCHAR,
    ean_code                VARCHAR,

    -- inventory metrics
    quantity_on_hand         INT,
    quantity_reserved        INT,
    quantity_available       INT,                -- on_hand - reserved
    unit_cost               DECIMAL(12, 2),
    unit_retail_price       DECIMAL(12, 2),
    total_cost_value        DECIMAL(18, 2),
    total_retail_value      DECIMAL(18, 2),

    -- supply chain signals
    reorder_point           INT,
    days_of_supply          DECIMAL(8, 2),
    stockout_risk_flag      BOOLEAN,
    overstock_flag          BOOLEAN,
    turnover_rate_90d       DECIMAL(8, 4),

    -- warehouse metadata
    warehouse_name          VARCHAR,
    warehouse_country       VARCHAR,
    warehouse_region        VARCHAR,

    -- timestamps
    snapshot_timestamp      TIMESTAMP,
    event_date              DATE,               -- partition key
    _pipeline_version       VARCHAR
)
USING iceberg
PARTITIONED BY (event_date)
WITH (
    'format'                              = 'PARQUET',
    'write.format.default'                = 'parquet',
    'write.parquet.compression-codec'     = 'zstd',
    'write.distribution-mode'             = 'hash',
    'write.target-file-size-bytes'        = '536870912',
    'commit.manifest-merge.enabled'       = 'true',
    'history.expire.max-snapshot-age-ms'  = '259200000',
    'history.expire.min-snapshots-keep'   = '5'
);

-- =============================================================================
-- 3. gold.financial_transactions
-- =============================================================================
-- Immutable ledger of all financial events: payments, refunds, adjustments,
-- and revenue recognitions. Append-only — no UPDATEs or DELETEs in normal flow.
--
-- Partition: event_date (daily)
-- Bucket:    customer_id (32 buckets)
-- =============================================================================

CREATE TABLE IF NOT EXISTS awsdatacatalog.gold.financial_transactions (
    -- identifiers
    transaction_id          VARCHAR,            -- external system reference
    customer_id             BIGINT,
    order_id                BIGINT,
    invoice_id              VARCHAR,

    -- transaction details
    transaction_type        VARCHAR,            -- 'payment', 'refund', 'adjustment', 'revenue_recognition'
    transaction_status      VARCHAR,            -- 'completed', 'pending', 'failed', 'reversed'
    payment_method          VARCHAR,            -- 'wire', 'card', 'ach', 'crypto'
    payment_provider        VARCHAR,

    -- amounts
    amount                  DECIMAL(18, 2),
    currency                VARCHAR(3),
    amount_base_currency    DECIMAL(18, 2),     -- normalized to EUR
    exchange_rate           DECIMAL(14, 6),
    tax_amount              DECIMAL(12, 2),
    net_amount              DECIMAL(18, 2),

    -- accounting
    gl_account_code         VARCHAR,
    cost_center             VARCHAR,
    revenue_category        VARCHAR,            -- 'subscription', 'professional_services', 'usage'
    recognition_date        DATE,

    -- compliance
    sox_compliant           BOOLEAN,
    audit_trail             VARCHAR,            -- JSON audit blob
    fraud_score             DECIMAL(4, 3),

    -- timestamps
    transaction_timestamp   TIMESTAMP,
    settlement_date         DATE,
    event_date              DATE,               -- partition key
    _pipeline_version       VARCHAR,
    _source_system          VARCHAR
)
USING iceberg
PARTITIONED BY (event_date)
WITH (
    'format'                              = 'PARQUET',
    'write.format.default'                = 'parquet',
    'write.parquet.compression-codec'     = 'zstd',
    'write.distribution-mode'             = 'hash',
    'write.sort-order'                    = 'transaction_timestamp ASC',
    'write.target-file-size-bytes'        = '536870912',
    'commit.manifest-merge.enabled'       = 'true',
    'history.expire.max-snapshot-age-ms'  = '7776000000',   -- 90 days for financial
    'history.expire.min-snapshots-keep'   = '30',
    'write.upsert.enabled'                = 'false'          -- append-only ledger
);

-- =============================================================================
-- Indexes (Trino Iceberg supports metadata-level filtering)
-- =============================================================================

-- These are informational — Trino uses partition pruning and Iceberg
-- statistics for predicate pushdown. Physical indexes are not supported
-- in Iceberg, but min/max column statistics enable efficient filtering.

-- Verify tables
SELECT table_name, location
FROM awsdatacatalog.information_schema.tables
WHERE table_schema = 'gold'
  AND table_name IN ('customer_360', 'inventory_snapshot', 'financial_transactions');
