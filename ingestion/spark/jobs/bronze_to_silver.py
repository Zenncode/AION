"""
AION Bronze → Silver Pipeline
==============================
Reads raw JSON from S3 Bronze bucket, validates with Great Expectations,
writes cleansed Parquet to S3 Silver bucket (Iceberg-managed).

Usage:
    spark-submit \
        --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,\
org.apache.hadoop:aws-hadoop:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf spark.sql.catalog.s3catalog=org.apache.iceberg.spark.SparkCatalog \
        --conf spark.sql.catalog.s3catalog.type=hadoop \
        --conf spark.sql.catalog.s3catalog.warehouse=s3a://aion-silver-lakehouse \
        --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.SparkSessionExtensions \
        --conf spark.sql.catalog.s3catalog.io-impl=org.apache.iceberg.aws.hadoop.HadoopFileIO \
        bronze_to_silver.py
"""

import os
import sys
import logging
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, LongType, IntegerType,
    NumericType, StringType, TimestampType
)

import great_expectations as gx
from great_expectations.core import ExpectationSuite
from great_expectations.expectations.core import (
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeBetween,
    ExpectColumnValuesToBeInSet,
    ExpectTableRowCountToBeBetween,
    ExpectColumnValuesToMatchRegex,
)

# =============================================================================
# Configuration
# =============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aion-bronze-to-silver")

BRONZE_BUCKET = os.getenv("BRONZE_BUCKET", "aion-bronze-raw")
SILVER_BUCKET = os.getenv("SILVER_BUCKET", "aion-silver-lakehouse")
SILVER_TABLE  = os.getenv("SILVER_TABLE", "orders_cleansed")
AWS_REGION    = os.getenv("AWS_REGION", "eu-west-1")

# S3 paths
BRONZE_PATH = f"s3a://{BRONZE_BUCKET}/orders/"
SILVER_PATH = f"s3a://{SILVER_BUCKET}/orders/"

# Expected schema for raw JSON
EXPECTED_SCHEMA = StructType([
    StructField("order_id",     LongType(),     False),
    StructField("customer_id",  LongType(),     False),
    StructField("product_id",   LongType(),     False),
    StructField("quantity",     IntegerType(),  False),
    StructField("unit_price",   NumericType(),  False),
    StructField("total_amount", NumericType(),  True),
    StructField("currency",     StringType(),   False),
    StructField("status",       StringType(),   False),
    StructField("region",       StringType(),   True),
    StructField("created_at",   StringType(),   True),
    StructField("updated_at",   StringType(),   True),
])

VALID_CURRENCIES = {"EUR", "USD", "GBP", "SEK", "NOK", "DKK"}
VALID_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled", "refunded"}


# =============================================================================
# Spark Session
# =============================================================================

def create_spark_session() -> SparkSession:
    """Create Spark session configured for S3 + Iceberg."""
    return (
        SparkSession.builder
        .appName("AION Bronze → Silver: Orders")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.legacy.timeParserPolicy", "CORRECT")
        .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_REGION}.amazonaws.com")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")
        .config("spark.sql.catalog.s3catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.s3catalog.type", "hadoop")
        .config("spark.sql.catalog.s3catalog.warehouse", f"s3a://{SILVER_BUCKET}")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.SparkSessionExtensions")
        .getOrCreate()
    )


# =============================================================================
# Data Reading
# =============================================================================

def read_bronze_data(spark: SparkSession):
    """Read raw JSON files from Bronze bucket with schema inference."""
    logger.info(f"Reading bronze data from: {BRONZE_PATH}")

    df = (
        spark.read
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .schema(EXPECTED_SCHEMA)
        .json(BRONZE_PATH)
    )

    record_count = df.count()
    logger.info(f"Read {record_count} records from Bronze")

    if record_count == 0:
        logger.warning("No records found in Bronze bucket. Returning empty DataFrame.")
        return df, 0

    return df, record_count


# =============================================================================
# Data Cleansing
# =============================================================================

def cleanse_data(df):
    """Apply cleansing transformations to raw data."""
    logger.info("Applying cleansing transformations...")

    cleansed = (
        df
        # Drop completely corrupt records
        .filter(F.col("_corrupt_record").isNull())
        .drop("_corrupt_record")

        # Trim string fields
        .withColumn("currency", F.trim(F.upper(F.col("currency"))))
        .withColumn("status", F.trim(F.lower(F.col("status"))))
        .withColumn("region", F.trim(F.lower(F.col("region"))))

        # Parse timestamps
        .withColumn("created_at_parsed",
                    F.to_timestamp(F.col("created_at"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"))
        .withColumn("updated_at_parsed",
                    F.to_timestamp(F.col("updated_at"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"))

        # Fallback timestamps for records missing them
        .withColumn("created_at_ts",
                    F.coalesce(F.col("created_at_parsed"), F.current_timestamp()))
        .withColumn("updated_at_ts",
                    F.coalesce(F.col("updated_at_parsed"), F.col("created_at_ts")))

        # Drop raw string timestamp columns and originals
        .drop("created_at", "updated_at", "created_at_parsed", "updated_at_parsed")

        # Rename parsed timestamps
        .withColumnRenamed("created_at_ts", "created_at")
        .withColumnRenamed("updated_at_ts", "updated_at")

        # Ensure numeric types are correct
        .withColumn("unit_price", F.col("unit_price").cast("decimal(12,2)"))
        .withColumn("total_amount",
                    F.coalesce(
                        F.col("total_amount"),
                        F.col("quantity") * F.col("unit_price")
                    ).cast("decimal(12,2)"))

        # Filter out invalid records
        .filter(F.col("order_id").isNotNull())
        .filter(F.col("customer_id").isNotNull())
        .filter(F.col("quantity") > 0)
        .filter(F.col("unit_price") > 0)
        .filter(F.col("currency").isin(*VALID_CURRENCIES))
        .filter(F.col("status").isin(*VALID_STATUSES))

        # Add processing metadata
        .withColumn("_processing_timestamp", F.current_timestamp())
        .withColumn("_source", F.lit("bronze-orders"))
        .withColumn("_pipeline_version", F.lit("1.0.0"))
        .withColumn("_record_date", F.to_date(F.col("created_at")))
    )

    cleansed_count = cleansed.count()
    logger.info(f"Cleansed: {cleansed_count} valid records")

    return cleansed


# =============================================================================
# Great Expectations Validation
# =============================================================================

def validate_with_great_expectations(spark, df):
    """
    Validate cleansed data using Great Expectations.
    Raises Exception if critical validations fail.
    """
    logger.info("Running Great Expectations validation suite...")

    context = gx.get_context()

    # Create expectation suite
    suite = ExpectationSuite(expectation_suite_name="orders_silver_suite")

    # Schema / nullability expectations
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="order_id"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="customer_id"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="product_id"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="quantity"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="unit_price"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="currency"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="status"))

    # Range expectations
    suite.add_expectation(ExpectColumnValuesToBeBetween(
        column="quantity", min_value=1, max_value=10000))
    suite.add_expectation(ExpectColumnValuesToBeBetween(
        column="unit_price", min_value=0.01, max_value=1000000.00))
    suite.add_expectation(ExpectColumnValuesToBeBetween(
        column="total_amount", min_value=0.01, max_value=10000000.00))

    # Categorical expectations
    suite.add_expectation(ExpectColumnValuesToBeInSet(
        column="currency", value_set=list(VALID_CURRENCIES)))
    suite.add_expectation(ExpectColumnValuesToBeInSet(
        column="status", value_set=list(VALID_STATUSES)))

    # Row count sanity check (at least 1 record, at most 10M)
    suite.add_expectation(ExpectTableRowCountToBeBetween(
        min_value=1, max_value=10_000_000))

    # Data quality expectations
    suite.add_expectation(ExpectColumnValuesToMatchRegex(
        column="currency", regex=r"^[A-Z]{3}$"))

    # Run validation using SparkDFDatasource
    data_source_name = "aion_spark_source"
    try:
        data_source = context.data_sources.add_spark(name=data_source_name)
    except Exception:
        data_source = context.data_sources.get(data_source_name)

    data_asset = data_source.add_dataframe_asset(
        name="orders_dataframe",
        dataframe=df,
    )

    batch_request = data_asset.build_batch_request()
    checkpoint = context.add_or_update_checkpoint(
        name="orders_checkpoint",
        validations=[{
            "batch_request": batch_request,
            "expectation_suite_name": "orders_silver_suite",
        }],
    )

    result = checkpoint.run()

    if not result.success:
        failed_expectations = [
            res for res in result.results if not res.success
        ]
        logger.error(f"Validation FAILED: {len(failed_expectations)} expectations failed")
        for exp in failed_expectations:
            logger.error(f"  - {exp.expectation_config.expectation_type}: "
                         f"{exp.expectation_config.kwargs}")

        # In production, raise to halt pipeline
        if os.getenv("STRICT_VALIDATION", "true").lower() == "true":
            raise ValueError(
                f"Great Expectations validation failed with "
                f"{len(failed_expectations)} failures. "
                f"Set STRICT_VALIDATION=false to bypass."
            )
        else:
            logger.warning("STRICT_VALIDATION=false — proceeding despite failures")
    else:
        logger.info("All expectation validations PASSED")

    return result.success


# =============================================================================
# Iceberg Write
# =============================================================================

def write_to_iceberg(spark, df):
    """Write cleansed DataFrame to Iceberg-managed Silver table."""
    logger.info(f"Writing to Iceberg table: s3catalog.aion.{SILVER_TABLE}")

    # Register temp view for Iceberg SQL
    df.createOrReplaceTempView("orders_staging")

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS s3catalog.aion.{SILVER_TABLE} (
            order_id        BIGINT,
            customer_id     BIGINT,
            product_id      BIGINT,
            quantity        INT,
            unit_price      DECIMAL(12,2),
            total_amount    DECIMAL(12,2),
            currency        STRING,
            status          STRING,
            region          STRING,
            created_at      TIMESTAMP,
            updated_at      TIMESTAMP,
            _processing_timestamp TIMESTAMP,
            _source         STRING,
            _pipeline_version STRING,
            _record_date    DATE
        )
        USING iceberg
        PARTITIONED BY (_record_date)
        TBLPROPERTIES (
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'zstd',
            'write.distribution-mode' = 'hash',
            'write.sort-order' = 'created_at ASC',
            'commit.manifest-merge.enabled' = 'true'
        )
    """)

    # Append to Iceberg table
    spark.sql(f"""
        INSERT INTO s3catalog.aion.{SILVER_TABLE}
        SELECT * FROM orders_staging
    """)

    written_count = spark.sql(
        f"SELECT COUNT(*) as cnt FROM s3catalog.aion.{SILVER_TABLE} "
        f"WHERE _record_date = current_date()"
    ).collect()[0]["cnt"]

    logger.info(f"Written {written_count} records to Iceberg Silver table")


# =============================================================================
# Main
# =============================================================================

def main():
    start_time = datetime.now(timezone.utc)
    logger.info("=== AION Bronze → Silver Pipeline Started ===")

    spark = create_spark_session()

    try:
        # 1. Read Bronze
        raw_df, raw_count = read_bronze_data(spark)

        if raw_count == 0:
            logger.warning("No data to process. Exiting.")
            return

        # 2. Cleanse
        cleansed_df = cleanse_data(raw_df)
        cleansed_count = cleansed_df.count()

        # 3. Validate
        validation_passed = validate_with_great_expectations(spark, cleansed_df)

        # 4. Write to Silver (Iceberg)
        write_to_iceberg(spark, cleansed_df)

        # 5. Summary
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("Pipeline Complete")
        logger.info(f"  Bronze records read:    {raw_count}")
        logger.info(f"  Silver records written: {cleansed_count}")
        logger.info(f"  Validation passed:      {validation_passed}")
        logger.info(f"  Duration:               {duration:.1f}s")
        logger.info(f"  Data loss:              {raw_count - cleansed_count} records "
                     f"({((raw_count - cleansed_count) / max(raw_count, 1) * 100):.1f}%)")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline FAILED: {e}", exc_info=True)
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
