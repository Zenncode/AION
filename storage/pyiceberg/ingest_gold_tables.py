"""
AION PyIceberg Ingestion — Append to Gold Tables
=================================================
Uses PyIceberg to append data to Iceberg tables with schema evolution enabled.

Usage:
    python ingest_gold_tables.py --table customer_360 --input data.parquet
    python ingest_gold_tables.py --table financial_transactions --input transactions.json
    python ingest_gold_tables.py --table inventory_snapshot --input inventory.csv

Environment:
    AWS_REGION              — AWS region (default: eu-west-1)
    GLUE_CATALOG_ID        — AWS account ID for Glue catalog
    WAREHOUSE_LOCATION     — S3 warehouse path (default: s3://aion-silver-lakehouse)
    AWS_ACCESS_KEY_ID      — (from IRSA or env)
    AWS_SECRET_ACCESS_KEY  — (from IRSA or env)
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.csv as pcsv
import pyarrow.json as pjson

from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, LongType, IntegerType,
    DecimalType, DateType, TimestampType, BooleanType,
    ListType, MapType
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform, BucketTransform
from pyiceberg.table import Table
from pyiceberg.io import PropertiesFileIO

# =============================================================================
# Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("aion-pyiceberg-ingest")

AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
GLUE_CATALOG_ID = os.getenv("GLUE_CATALOG_ID", "")
WAREHOUSE_LOCATION = os.getenv("WAREHOUSE_LOCATION", "s3://aion-silver-lakehouse")
SCHEMA_EVOLUTION = os.getenv("SCHEMA_EVOLUTION", "true").lower() == "true"


# =============================================================================
# Iceberg Schemas (must match DDL)
# =============================================================================

CUSTOMER_360_SCHEMA = Schema(
    NestedField(1, "customer_id",            LongType(),             required=True),
    NestedField(2, "customer_name",          StringType(),           required=False),
    NestedField(3, "email",                  StringType(),           required=False),
    NestedField(4, "segment",                StringType(),           required=False),
    NestedField(5, "tier",                   StringType(),           required=False),
    NestedField(6, "country",                StringType(),           required=False),
    NestedField(7, "region",                 StringType(),           required=False),
    NestedField(8, "total_orders_12m",       LongType(),             required=False),
    NestedField(9, "total_revenue_12m",      DecimalType(18, 2),     required=False),
    NestedField(10, "avg_order_value_12m",   DecimalType(12, 2),     required=False),
    NestedField(11, "total_orders_30d",      LongType(),             required=False),
    NestedField(12, "total_revenue_30d",     DecimalType(18, 2),     required=False),
    NestedField(13, "days_since_last_order", IntegerType(),          required=False),
    NestedField(14, "active_products",       IntegerType(),          required=False),
    NestedField(15, "rfm_recency_score",     IntegerType(),          required=False),
    NestedField(16, "rfm_frequency_score",   IntegerType(),          required=False),
    NestedField(17, "rfm_monetary_score",    IntegerType(),          required=False),
    NestedField(18, "rfm_composite_score",   DecimalType(4, 2),      required=False),
    NestedField(19, "churn_risk_score",      DecimalType(4, 3),      required=False),
    NestedField(20, "predicted_ltv",         DecimalType(14, 2),     required=False),
    NestedField(21, "gdpr_consent",          BooleanType(),          required=False),
    NestedField(22, "ccpa_opt_out",          BooleanType(),          required=False),
    NestedField(23, "event_date",            DateType(),             required=True),
    NestedField(24, "record_updated_at",     TimestampType(),        required=False),
    NestedField(25, "_pipeline_version",     StringType(),           required=False),
    NestedField(26, "_source_systems",       ListType(1, StringType(), element_required=False), required=False),
)

INVENTORY_SNAPSHOT_SCHEMA = Schema(
    NestedField(1,  "snapshot_id",           LongType(),             required=True),
    NestedField(2,  "product_id",            LongType(),             required=True),
    NestedField(3,  "warehouse_id",          LongType(),             required=True),
    NestedField(4,  "customer_id",           LongType(),             required=False),
    NestedField(5,  "product_name",          StringType(),           required=False),
    NestedField(6,  "product_category",      StringType(),           required=False),
    NestedField(7,  "sku",                   StringType(),           required=False),
    NestedField(8,  "ean_code",              StringType(),           required=False),
    NestedField(9,  "quantity_on_hand",      IntegerType(),          required=False),
    NestedField(10, "quantity_reserved",     IntegerType(),          required=False),
    NestedField(11, "quantity_available",    IntegerType(),          required=False),
    NestedField(12, "unit_cost",             DecimalType(12, 2),     required=False),
    NestedField(13, "unit_retail_price",     DecimalType(12, 2),     required=False),
    NestedField(14, "total_cost_value",      DecimalType(18, 2),     required=False),
    NestedField(15, "total_retail_value",    DecimalType(18, 2),     required=False),
    NestedField(16, "reorder_point",         IntegerType(),          required=False),
    NestedField(17, "days_of_supply",        DecimalType(8, 2),      required=False),
    NestedField(18, "stockout_risk_flag",    BooleanType(),          required=False),
    NestedField(19, "overstock_flag",        BooleanType(),          required=False),
    NestedField(20, "turnover_rate_90d",     DecimalType(8, 4),      required=False),
    NestedField(21, "warehouse_name",        StringType(),           required=False),
    NestedField(22, "warehouse_country",     StringType(),           required=False),
    NestedField(23, "warehouse_region",      StringType(),           required=False),
    NestedField(24, "snapshot_timestamp",    TimestampType(),        required=False),
    NestedField(25, "event_date",            DateType(),             required=True),
    NestedField(26, "_pipeline_version",     StringType(),           required=False),
)

FINANCIAL_TRANSACTIONS_SCHEMA = Schema(
    NestedField(1,  "transaction_id",        StringType(),           required=True),
    NestedField(2,  "customer_id",           LongType(),             required=True),
    NestedField(3,  "order_id",              LongType(),             required=False),
    NestedField(4,  "invoice_id",            StringType(),           required=False),
    NestedField(5,  "transaction_type",      StringType(),           required=False),
    NestedField(6,  "transaction_status",    StringType(),           required=False),
    NestedField(7,  "payment_method",        StringType(),           required=False),
    NestedField(8,  "payment_provider",      StringType(),           required=False),
    NestedField(9,  "amount",                DecimalType(18, 2),     required=False),
    NestedField(10, "currency",              StringType(),           required=False),
    NestedField(11, "amount_base_currency",  DecimalType(18, 2),     required=False),
    NestedField(12, "exchange_rate",         DecimalType(14, 6),     required=False),
    NestedField(13, "tax_amount",            DecimalType(12, 2),     required=False),
    NestedField(14, "net_amount",            DecimalType(18, 2),     required=False),
    NestedField(15, "gl_account_code",       StringType(),           required=False),
    NestedField(16, "cost_center",           StringType(),           required=False),
    NestedField(17, "revenue_category",      StringType(),           required=False),
    NestedField(18, "recognition_date",      DateType(),             required=False),
    NestedField(19, "sox_compliant",         BooleanType(),          required=False),
    NestedField(20, "audit_trail",           StringType(),           required=False),
    NestedField(21, "fraud_score",           DecimalType(4, 3),      required=False),
    NestedField(22, "transaction_timestamp", TimestampType(),        required=False),
    NestedField(23, "settlement_date",       DateType(),             required=False),
    NestedField(24, "event_date",            DateType(),             required=True),
    NestedField(25, "_pipeline_version",     StringType(),           required=False),
    NestedField(26, "_source_system",        StringType(),           required=False),
)

# Table name → (schema, location suffix, partition fields)
TABLE_REGISTRY = {
    "customer_360": {
        "schema": CUSTOMER_360_SCHEMA,
        "location": "gold/customer_360",
        "partition": ["event_date"],
        "bucket": "customer_id",
    },
    "inventory_snapshot": {
        "schema": INVENTORY_SNAPSHOT_SCHEMA,
        "location": "gold/inventory_snapshot",
        "partition": ["event_date"],
        "bucket": "customer_id",
    },
    "financial_transactions": {
        "schema": FINANCIAL_TRANSACTIONS_SCHEMA,
        "location": "gold/financial_transactions",
        "partition": ["event_date"],
        "bucket": "customer_id",
    },
}


# =============================================================================
# Catalog Connection
# =============================================================================

def get_catalog():
    """Load Glue catalog with IRSA or env credentials."""
    properties = {
        "type": "glue",
        "glue.region": AWS_REGION,
        "warehouse": WAREHOUSE_LOCATION,
        "s3.region": AWS_REGION,
        "s3.endpoint": f"s3.{AWS_REGION}.amazonaws.com",
        "s3.path-style-access": "true",
        "io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
    }

    if GLUE_CATALOG_ID:
        properties["glue.account-id"] = GLUE_CATALOG_ID

    # IRSA injects AWS_* env vars automatically; no explicit keys needed on EKS.
    # For local dev, fall back to env or default credentials chain.
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    if access_key and secret_key:
        properties["s3.access-key-id"] = access_key
        properties["s3.secret-access-key"] = secret_key
        if session_token:
            properties["s3.session-token"] = session_token

    logger.info("Loading Glue catalog: region=%s, warehouse=%s", AWS_REGION, WAREHOUSE_LOCATION)
    return load_catalog("glue", **properties)


def get_or_create_table(catalog, table_name: str) -> Table:
    """Get existing table or create it if it doesn't exist."""
    db = "aion"
    full_name = f"{db}.{table_name}"

    if catalog.table_exists(full_name):
        logger.info("Table exists: %s", full_name)
        table = catalog.load_table(full_name)
        logger.info("Current schema: %s", table.schema())
        logger.info("Current spec: %s", table.spec())
        return table

    # Create table
    config = TABLE_REGISTRY[table_name]
    schema = config["schema"]
    location = f"{WAREHOUSE_LOCATION}/{config['location']}"

    # Build partition spec
    field_id = len(schema.fields) + 1
    partition_fields = []
    for i, field_name in enumerate(config["partition"]):
        field = schema.find_field(field_name)
        transform = DayTransform()
        pf = PartitionField(
            source_id=field.field_id,
            field_id=field_id + i,
            transform=transform,
            name=f"{field_name}_day"
        )
        partition_fields.append(pf)

    spec = PartitionSpec(*partition_fields)

    logger.info("Creating table: %s at %s", full_name, location)
    table = catalog.create_table(
        identifier=full_name,
        schema=schema,
        location=location,
        partition_spec=spec,
        properties={
            "format": "PARQUET",
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",
            "write.distribution-mode": "hash",
            "write.target-file-size-bytes": "536870912",
            "commit.manifest-merge.enabled": "true",
        },
    )
    logger.info("Table created: %s", full_name)
    return table


# =============================================================================
# Data Loading
# =============================================================================

def load_data(file_path: str, file_format: str = "parquet") -> pa.Table:
    """Load data from Parquet, CSV, or JSON file into PyArrow Table."""
    path = Path(file_path)
    logger.info("Loading data: %s (format=%s)", path, file_format)

    if file_format == "parquet" or path.suffix == ".parquet":
        table = pq.read_table(str(path))
    elif file_format == "csv" or path.suffix == ".csv":
        table = pcsv.read_csv(str(path))
    elif file_format == "json" or path.suffix in (".json", ".jsonl"):
        table = pjson.read_json(str(path))
    else:
        raise ValueError(f"Unsupported format: {file_format}")

    logger.info("Loaded %d rows, %d columns", table.num_rows, table.num_columns)
    return table


def convert_to_iceberg_types(arrow_table: pa.Table, iceberg_schema: Schema) -> pa.Table:
    """Cast Arrow columns to match the Iceberg schema types."""
    logger.info("Converting Arrow types to Iceberg schema...")

    for field in iceberg_schema.fields:
        col_name = field.name
        if col_name not in arrow_table.column_names:
            logger.warning("Column '%s' not in input data — skipping", col_name)
            continue

        iceberg_type = field.type
        current_type = arrow_table.schema.field(col_name).type

        target_arrow_type = _iceberg_to_arrow_type(iceberg_type)

        if target_arrow_type and current_type != target_arrow_type:
            logger.info("  Casting %s: %s → %s", col_name, current_type, target_arrow_type)
            arrow_table = arrow_table.set_column(
                arrow_table.column_names.index(col_name),
                col_name,
                arrow_table.column(col_name).cast(target_arrow_type, safe=False)
            )

    return arrow_table


def _iceberg_to_arrow_type(iceberg_type):
    """Map Iceberg types to PyArrow types."""
    from pyiceberg.types import (
        StringType as IceString, LongType as IceLong,
        IntegerType as IceInt, DecimalType as IceDecimal,
        DateType as IceDate, TimestampType as IceTimestamp,
        BooleanType as IceBoolean
    )

    if isinstance(iceberg_type, IceString):
        return pa.string()
    elif isinstance(iceberg_type, IceLong):
        return pa.int64()
    elif isinstance(iceberg_type, IceInt):
        return pa.int32()
    elif isinstance(iceberg_type, IceDecimal):
        return pa.decimal128(iceberg_type.precision, iceberg_type.scale)
    elif isinstance(iceberg_type, IceDate):
        return pa.date32()
    elif isinstance(iceberg_type, IceTimestamp):
        return pa.timestamp("us", tz="UTC")
    elif isinstance(iceberg_type, IceBoolean):
        return pa.bool_()
    return None


# =============================================================================
# Schema Evolution
# =============================================================================

def apply_schema_evolution(table: Table, new_arrow_table: pa.Table):
    """
    Detect new columns in incoming data and evolve the Iceberg schema.
    Only adds columns — never removes or reorders.
    """
    if not SCHEMA_EVOLUTION:
        return

    iceberg_schema = table.schema()
    existing_cols = {f.name for f in iceberg_schema.fields}
    incoming_cols = set(new_arrow_table.column_names)

    new_cols = incoming_cols - existing_cols

    if not new_cols:
        return

    logger.info("Schema evolution: adding %d new columns: %s", len(new_cols), new_cols)

    # Find max field ID
    max_id = max(f.field_id for f in iceberg_schema.fields)

    for col_name in sorted(new_cols):
        col_type = new_arrow_table.schema.field(col_name).type
        iceberg_type = _arrow_to_iceberg_type(col_type)
        new_id = max_id + 1
        max_id = new_id

        new_field = NestedField(
            field_id=new_id,
            name=col_name,
            field_type=iceberg_type,
            required=False
        )

        logger.info("  Adding column: %s (id=%d, type=%s)", col_name, new_id, iceberg_type)
        table.update_schema().add_column(new_field).commit()

    logger.info("Schema evolution complete")


def _arrow_to_iceberg_type(arrow_type):
    """Map PyArrow types to Iceberg types."""
    from pyiceberg.types import (
        StringType, LongType, IntegerType, DecimalType,
        DateType, TimestampType, BooleanType
    )

    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        return StringType()
    elif pa.types.is_int64(arrow_type):
        return LongType()
    elif pa.types.is_int32(arrow_type):
        return IntegerType()
    elif pa.types.is_decimal(arrow_type):
        return DecimalType(arrow_type.precision, arrow_type.scale)
    elif pa.types.is_date(arrow_type):
        return DateType()
    elif pa.types.is_timestamp(arrow_type):
        return TimestampType()
    elif pa.types.is_boolean(arrow_type):
        return BooleanType()
    return StringType()  # fallback


# =============================================================================
# Append to Table
# =============================================================================

def append_to_table(table: Table, arrow_table: pa.Table, event_date: date):
    """
    Append data to Iceberg table.
    - Casts types to match schema
    - Applies schema evolution if new columns detected
    - Partitions by event_date
    """
    # Ensure event_date column exists
    if "event_date" not in arrow_table.column_names:
        arrow_table = arrow_table.append_column(
            "event_date", pa.array([event_date] * arrow_table.num_rows, type=pa.date32())
        )

    # Convert types
    arrow_table = convert_to_iceberg_types(arrow_table, table.schema())

    # Add pipeline metadata
    now = datetime.now(timezone.utc)
    version = os.getenv("PIPELINE_VERSION", "1.0.0")

    if "_pipeline_version" not in arrow_table.column_names:
        arrow_table = arrow_table.append_column(
            "_pipeline_version",
            pa.array([version] * arrow_table.num_rows, type=pa.string())
        )

    # Apply schema evolution
    apply_schema_evolution(table, arrow_table)

    # Re-read table after potential schema evolution
    table = table.catalog.load_table(table.identifier)

    # Append
    logger.info("Appending %d rows to %s (event_date=%s)",
                arrow_table.num_rows, table.identifier, event_date)

    insert = table.append(arrow_table)

    logger.info("Append complete: %d new files written", len(insert.manifest_files()))
    return insert


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="AION PyIceberg: Append data to Gold Iceberg tables"
    )
    parser.add_argument(
        "--table",
        required=True,
        choices=list(TABLE_REGISTRY.keys()),
        help="Target Iceberg table name"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input file (Parquet, CSV, or JSON)"
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default=None,
        help="Input file format (auto-detected from extension if omitted)"
    )
    parser.add_argument(
        "--event-date",
        default=None,
        help="Event date for partition (YYYY-MM-DD). Defaults to today."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate schema and data without writing"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("AION PyIceberg Ingestion — Gold Tables")
    logger.info("=" * 60)

    # Resolve event date
    if args.event_date:
        event_date = date.fromisoformat(args.event_date)
    else:
        event_date = date.today()

    # Auto-detect format
    file_format = args.format
    if not file_format:
        suffix = Path(args.input).suffix.lower()
        format_map = {".parquet": "parquet", ".csv": "csv", ".json": "json", ".jsonl": "json"}
        file_format = format_map.get(suffix, "parquet")

    # Connect to catalog
    catalog = get_catalog()

    # Get or create table
    table = get_or_create_table(catalog, args.table)

    # Load data
    arrow_table = load_data(args.input, file_format)

    if arrow_table.num_rows == 0:
        logger.warning("Input file is empty — nothing to append")
        sys.exit(0)

    # Dry run
    if args.dry_run:
        logger.info("DRY RUN — validating schema only")
        converted = convert_to_iceberg_types(arrow_table, table.schema())
        logger.info("Schema validation passed. Rows: %d", converted.num_rows)
        logger.info("Converted schema: %s", converted.schema)
        sys.exit(0)

    # Append
    result = append_to_table(table, arrow_table, event_date)

    logger.info("=" * 60)
    logger.info("Ingestion complete")
    logger.info("  Table:  %s", table.identifier)
    logger.info("  Rows:   %d", arrow_table.num_rows)
    logger.info("  Date:   %s", event_date)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
