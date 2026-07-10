"""
AION Feast Feature Store — Feature Definitions
================================================
Defines feature views sourced from Iceberg Gold tables,
served via Redis online store for real-time inference.

Catalog:    AWS Glue (Iceberg metadata)
Source:     gold.customer_360 (batch source)
Online:     Redis cluster
Registry:   S3-backed (Glue-backed for production)
"""

from datetime import timedelta
from feast import (
    Entity,
    FeatureView,
    Field,
    FileSource,
    PushSource,
    BatchFeatureView,
)
from feast.types import Float32, Int64, String, Bool, Float64
from feast.infra.offline_stores.contrib.glue_offline_store.config import (
    AthenaOfflineStoreConfig,
)
from feast.infra.offline_stores.glue import GlueOfflineStoreConfig
from feast.infra.online_stores.redis import RedisOnlineStoreConfig
from feast.repo_config import RegistryConfig
import os

# =============================================================================
# Environment
# =============================================================================

AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
REGISTRY_PATH = os.getenv("FEAST_REGISTRY_PATH", "s3://aion-feast-registry")
S3_ENDPOINT = f"s3.{AWS_REGION}.amazonaws.com"


# =============================================================================
# Entities
# =============================================================================

customer = Entity(
    name="customer_id",
    join_keys=["customer_id"],
    description="Unique customer identifier from AION Gold customer_360",
    value_type=Int64,
)


# =============================================================================
# Data Sources — Iceberg Gold via Glue
# =============================================================================

# Batch source: reads from the Iceberg table via AWS Glue catalog
# Feast queries Glue/Athena for offline retrieval and pushes to Redis for online
customer_360_batch_source = FileSource(
    name="customer_360_batch",
    path="s3://aion-gold-lakehouse/gold/customer_360/",
    timestamp_field="record_updated_at",
    event_timestamp_column="event_date",
    created_timestamp_column="record_updated_at",
    file_format="parquet",
    s3_endpoint_override=S3_ENDPOINT,
    data_catalog_table="aion.gold.customer_360",
)

# Push source for real-time feature updates (e.g., from Flink aggregation)
customer_activity_push_source = PushSource(
    name="customer_activity_push",
    batch_source=customer_360_batch_source,
    description="Real-time customer activity updates from Flink aggregation pipeline",
)


# =============================================================================
# Feature Views
# =============================================================================

user_activity_features = FeatureView(
    name="user_activity_features",
    entities=[customer],
    schema=[
        # 7-day rolling click rate (0.0 - 1.0)
        Field(
            name="click_rate_7d",
            dtype=Float32,
            description="Rolling 7-day click-through rate: total clicks / total impressions",
        ),

        # Average transaction value over 30 days
        Field(
            name="avg_transaction_value",
            dtype=Float64,
            description="Average transaction value (net amount) over the last 30 days in base currency",
        ),

        # Supporting features for churn model
        Field(
            name="total_orders_30d",
            dtype=Int64,
            description="Number of orders placed in the last 30 days",
        ),
        Field(
            name="total_revenue_30d",
            dtype=Float64,
            description="Total revenue (net) in the last 30 days",
        ),
        Field(
            name="days_since_last_order",
            dtype=Int64,
            description="Days since the customer's most recent order",
        ),
        Field(
            name="rfm_composite_score",
            dtype=Float32,
            description="Composite RFM (Recency, Frequency, Monetary) score: 1.0 - 5.0",
        ),
        Field(
            name="churn_risk_score",
            dtype=Float32,
            description="ML-predicted churn probability: 0.0 - 1.0",
        ),
        Field(
            name="segment",
            dtype=String,
            description="Customer segment: enterprise, smb, consumer",
        ),
        Field(
            name="tier",
            dtype=String,
            description="Customer tier: platinum, gold, silver, bronze",
        ),
        Field(
            name="gdpr_consent",
            dtype=Bool,
            description="Whether customer has given GDPR consent for data processing",
        ),
    ],
    source=customer_360_batch_source,
    description=(
        "7-day rolling customer activity features for churn prediction and "
        "real-time personalization. Sourced from gold.customer_360 Iceberg table."
    ),
    online=True,
    owner="aion-ml-team@aion.com",
    tags={
        "domain": "customer",
        "use_case": "churn_prediction",
        "tier": "gold",
        "freshness": "daily",
    },
    schema_version=1,
)


# =============================================================================
# Batch Feature View — Inventory Features
# =============================================================================

inventory_features_view = FeatureView(
    name="inventory_features",
    entities=[
        Entity(name="product_id", join_keys=["product_id"], value_type=Int64),
    ],
    schema=[
        Field(name="quantity_on_hand", dtype=Int64),
        Field(name="quantity_reserved", dtype=Int64),
        Field(name="days_of_supply", dtype=Float32),
        Field(name="stockout_risk_flag", dtype=Bool),
        Field(name="turnover_rate_90d", dtype=Float32),
    ],
    source=FileSource(
        name="inventory_snapshot_source",
        path="s3://aion-gold-lakehouse/gold/inventory_snapshot/",
        timestamp_field="snapshot_timestamp",
        file_format="parquet",
    ),
    online=True,
    description="Inventory position features for demand forecasting",
    tags={"domain": "supply_chain", "tier": "gold"},
)


# =============================================================================
# Stream Feature View — Real-time aggregation
# =============================================================================

# This captures the Flink-aggregated sales from Kafka topic aggregated.sales
stream_customer_sales_features = FeatureView(
    name="stream_customer_sales_features",
    entities=[customer],
    schema=[
        Field(name="window_total_revenue", dtype=Float64),
        Field(name="window_order_count", dtype=Int64),
        Field(name="window_avg_order_value", dtype=Float64),
        Field(name="window_unique_products", dtype=Int64),
    ],
    source=customer_activity_push_source,
    description=(
        "Real-time 5-minute tumbling window sales aggregates from Flink. "
        "Pushed via Kafka → PushSource for sub-second online serving."
    ),
    online=True,
    tags={"domain": "sales", "freshness": "streaming", "tier": "gold"},
)
