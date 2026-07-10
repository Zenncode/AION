-- =============================================================================
-- AION Materialized Views — Sub-second Executive Dashboard
-- =============================================================================
-- These views are persisted as Iceberg tables with automatic refresh.
-- Trino does not natively persist materialized views to Iceberg, so these
-- are implemented as:
--   1. A regular VIEW for logical abstraction
--   2. A scheduled Spark/Trino INSERT for physical persistence
--   3. A Trino table that reads the persisted snapshot
-- =============================================================================

-- =============================================================================
-- 1. dashboard_executive_kpi
-- =============================================================================
-- Pre-joins customer_360 + financial_transactions for executive dashboards.
-- Refreshed hourly via Airflow DAG.
-- =============================================================================

CREATE OR REPLACE VIEW awsdatacatalog.gold.dashboard_executive_kpi AS
WITH

-- Aggregate financial metrics per customer for current month
customer_finance AS (
    SELECT
        ft.customer_id,
        ft.event_date,

        -- Revenue
        SUM(CASE WHEN ft.transaction_type = 'payment'
                 THEN ft.net_amount ELSE 0 END)          AS mtd_revenue,
        SUM(CASE WHEN ft.transaction_type = 'refund'
                 THEN ABS(ft.net_amount) ELSE 0 END)     AS mtd_refunds,
        SUM(CASE WHEN ft.transaction_type = 'payment'
                 THEN ft.net_amount ELSE 0 END)
        - SUM(CASE WHEN ft.transaction_type = 'refund'
                   THEN ABS(ft.net_amount) ELSE 0 END)   AS mtd_net_revenue,

        -- Transaction counts
        COUNT(*)                                          AS total_transactions,
        COUNT(CASE WHEN ft.transaction_status = 'completed'
                  THEN 1 END)                             AS completed_transactions,
        COUNT(CASE WHEN ft.transaction_status = 'failed'
                  THEN 1 END)                             AS failed_transactions,

        -- Risk
        AVG(ft.fraud_score)                               AS avg_fraud_score,
        MAX(ft.fraud_score)                               AS max_fraud_score,

        -- Payment mix
        COUNT(DISTINCT ft.payment_method)                 AS payment_methods_used,
        COUNT(DISTINCT ft.invoice_id)                     AS distinct_invoices

    FROM awsdatacatalog.gold.financial_transactions ft
    WHERE ft.event_date >= DATE_TRUNC('month', CURRENT_DATE)
      AND ft.transaction_status != 'reversed'
    GROUP BY ft.customer_id, ft.event_date
),

-- Aggregate inventory metrics per customer (bulk orders)
customer_inventory AS (
    SELECT
        inv.customer_id,
        SUM(inv.quantity_on_hand)                         AS total_units_on_hand,
        SUM(inv.quantity_reserved)                        AS total_units_reserved,
        SUM(inv.total_cost_value)                        AS total_inventory_cost,
        SUM(inv.total_retail_value)                      AS total_inventory_retail,
        COUNT(DISTINCT inv.product_id)                   AS distinct_products,
        COUNT(DISTINCT inv.warehouse_id)                 AS warehouses_used,
        COUNT(CASE WHEN inv.stockout_risk_flag = TRUE
                  THEN 1 END)                             AS stockout_risk_items,
        COUNT(CASE WHEN inv.overstock_flag = TRUE
                  THEN 1 END)                             AS overstock_items,
        AVG(inv.turnover_rate_90d)                       AS avg_turnover_rate
    FROM awsdatacatalog.gold.inventory_snapshot inv
    WHERE inv.event_date = CURRENT_DATE
      AND inv.customer_id IS NOT NULL
    GROUP BY inv.customer_id
),

-- Combine customer profile + finance + inventory
executive_kpi AS (
    SELECT
        -- Customer identity
        c.customer_id,
        c.customer_name,
        c.segment,
        c.tier,
        c.country,
        c.region,

        -- RFM & CLV
        c.rfm_composite_score,
        c.churn_risk_score,
        c.predicted_ltv,

        -- Transactional (30-day)
        c.total_orders_30d,
        c.total_revenue_30d,
        c.avg_order_value_12m,
        c.days_since_last_order,

        -- Financial (MTD)
        COALESCE(f.mtd_revenue, 0)                        AS mtd_revenue,
        COALESCE(f.mtd_refunds, 0)                        AS mtd_refunds,
        COALESCE(f.mtd_net_revenue, 0)                    AS mtd_net_revenue,
        COALESCE(f.total_transactions, 0)                 AS mtd_transactions,
        COALESCE(f.completed_transactions, 0)             AS mtd_completed,
        COALESCE(f.failed_transactions, 0)                AS mtd_failed,
        COALESCE(f.avg_fraud_score, 0)                    AS avg_fraud_score,

        -- Inventory
        COALESCE(i.total_units_on_hand, 0)                AS inventory_on_hand,
        COALESCE(i.total_inventory_cost, 0)               AS inventory_cost,
        COALESCE(i.total_inventory_retail, 0)             AS inventory_retail,
        COALESCE(i.distinct_products, 0)                  AS inventory_products,
        COALESCE(i.stockout_risk_items, 0)                AS stockout_risks,
        COALESCE(i.avg_turnover_rate, 0)                  AS avg_turnover_rate,

        -- Derived KPIs
        CASE
            WHEN c.predicted_ltv > 0
            THEN ROUND(COALESCE(f.mtd_net_revenue, 0) / c.predicted_ltv, 4)
            ELSE 0
        END                                               AS revenue_vs_ltv_ratio,

        CASE
            WHEN c.total_revenue_12m > 0
            THEN ROUND(
                (c.total_revenue_30d * 12.0) / c.total_revenue_12m, 2)
            ELSE 0
        END                                               AS annualized_revenue_trend,

        CASE
            WHEN c.rfm_composite_score >= 4.0 THEN 'champion'
            WHEN c.rfm_composite_score >= 3.0 THEN 'loyal'
            WHEN c.rfm_composite_score >= 2.0 THEN 'at_risk'
            ELSE 'dormant'
        END                                               AS customer_health_label,

        -- Metadata
        c.event_date                                      AS profile_date,
        CURRENT_TIMESTAMP                                 AS refresh_timestamp

    FROM awsdatacatalog.gold.customer_360 c
    LEFT JOIN customer_finance f ON c.customer_id = f.customer_id
    LEFT JOIN customer_inventory i ON c.customer_id = i.customer_id
    WHERE c.event_date = (SELECT MAX(event_date) FROM awsdatacatalog.gold.customer_360)
)

SELECT * FROM executive_kpi;


-- =============================================================================
-- 2. Persisted snapshot table for sub-second queries
-- =============================================================================
-- The view above is computed on-the-fly. For dashboards requiring <100ms
-- latency, we persist the result into a materialized Iceberg table.
-- This table is refreshed by the Airflow DAG every hour.
-- =============================================================================

CREATE TABLE IF NOT EXISTS awsdatacatalog.gold.dashboard_executive_kpi_snapshot (
    customer_id             BIGINT,
    customer_name           VARCHAR,
    segment                 VARCHAR,
    tier                    VARCHAR,
    country                 VARCHAR,
    region                  VARCHAR,

    rfm_composite_score     DECIMAL(4, 2),
    churn_risk_score        DECIMAL(4, 3),
    predicted_ltv           DECIMAL(14, 2),

    total_orders_30d        BIGINT,
    total_revenue_30d       DECIMAL(18, 2),
    avg_order_value_12m     DECIMAL(12, 2),
    days_since_last_order   INT,

    mtd_revenue             DECIMAL(18, 2),
    mtd_refunds             DECIMAL(18, 2),
    mtd_net_revenue         DECIMAL(18, 2),
    mtd_transactions        BIGINT,
    mtd_completed           BIGINT,
    mtd_failed              BIGINT,
    avg_fraud_score         DECIMAL(4, 3),

    inventory_on_hand       INT,
    inventory_cost          DECIMAL(18, 2),
    inventory_retail        DECIMAL(18, 2),
    inventory_products      INT,
    stockout_risks          INT,
    avg_turnover_rate       DECIMAL(8, 4),

    revenue_vs_ltv_ratio    DECIMAL(8, 4),
    annualized_revenue_trend DECIMAL(8, 2),
    customer_health_label   VARCHAR,

    profile_date            DATE,
    refresh_timestamp       TIMESTAMP
)
USING iceberg
PARTITIONED BY (profile_date)
WITH (
    'format'                              = 'PARQUET',
    'write.format.default'                = 'parquet',
    'write.parquet.compression-codec'     = 'zstd',
    'write.distribution-mode'             = 'hash',
    'write.target-file-size-bytes'        = '268435456',
    'commit.manifest-merge.enabled'       = 'true',
    'history.expire.max-snapshot-age-ms'  = '259200000'
);


-- =============================================================================
-- 3. Refresh procedure (called by Airflow SparkSubmitOperator)
-- =============================================================================
-- This SQL is executed by Trino or Spark on each refresh cycle.
-- =============================================================================

-- Full overwrite (simple, correct for small tables)
-- INSERT OVERWRITE INTO awsdatacatalog.gold.dashboard_executive_kpi_snapshot
-- SELECT * FROM awsdatacatalog.gold.dashboard_executive_kpi;
