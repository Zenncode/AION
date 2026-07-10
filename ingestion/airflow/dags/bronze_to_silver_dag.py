"""
AION Airflow DAG — SparkSubmitOperator for Bronze → Silver Pipeline
=====================================================================

Submits the PySpark bronze_to_silver job to the Spark cluster on schedule.
Uses SparkSubmitOperator (not SparkJDBC or external task sensor).

Schedule: Daily at 02:00 UTC (after CDC batch lands)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable

# =============================================================================
# Configuration
# =============================================================================

SPARK_MASTER = Variable.get("spark_master_url", default_var="spark://spark-master:7077")
SPARK_HOME = Variable.get("spark_home", default_var="/opt/bitnami/spark")

SPARK_CONFIG = {
    "total-executor-cores": "4",
    "executor-cores": "2",
    "executor-memory": "3g",
    "driver-memory": "1g",
    "conf": {
        "spark.sql.shuffle.partitions": "8",
        "spark.sql.sources.partitionOverwriteMode": "dynamic",
        "spark.sql.session.timeZone": "UTC",
        "spark.hadoop.fs.s3a.endpoint": "s3.eu-west-1.amazonaws.com",
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.aws.credentials.provider":
            "com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
        # Iceberg
        "spark.sql.catalog.s3catalog": "org.apache.iceberg.spark.SparkCatalog",
        "spark.sql.catalog.s3catalog.type": "hadoop",
        "spark.sql.catalog.s3catalog.warehouse": "s3a://aion-silver-lakehouse",
        "spark.sql.extensions": "org.apache.iceberg.spark.extensions.SparkSessionExtensions",
        "spark.sql.catalog.s3catalog.io-impl":
            "org.apache.iceberg.aws.hadoop.HadoopFileIO",
    },
}

SPARK_PACKAGES = ",".join([
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3",
    "org.apache.hadoop:aws-hadoop:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
])

DEFAULT_ARGS = {
    "owner": "aion-data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["aion-alerts@example.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
    "sla": timedelta(hours=3),
}

# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id="aion_bronze_to_silver_orders",
    default_args=DEFAULT_ARGS,
    description="AION: Spark Bronze → Silver pipeline for orders with Great Expectations validation",
    schedule_interval="0 2 * * *",    # Daily at 02:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["aion", "spark", "silver", "iceberg", "data-quality"],
    doc_md="""
    ## AION Bronze → Silver Pipeline

    Reads raw JSON orders from S3 Bronze, validates schema and data quality
    using Great Expectations, and writes cleansed Parquet to Iceberg-managed
    S3 Silver bucket.

    ### Schedule
    - Runs daily at 02:00 UTC
    - Max 1 concurrent run
    - 2-hour execution timeout

    ### Alerts
    - Email on failure to aion-alerts@example.com
    - SLA: 3 hours
    """,
) as dag:

    # -------------------------------------------------------------------------
    # Pre-check: verify Bronze data exists
    # -------------------------------------------------------------------------

    def check_bronze_data(**context):
        """Verify new data is available in Bronze bucket before submitting Spark job."""
        import boto3

        s3 = boto3.client("s3")
        bucket = "aion-bronze-raw"

        response = s3.list_objects_v2(Bucket=bucket, Prefix="orders/", MaxKeys=10)
        contents = response.get("Contents", [])

        if not contents:
            raise ValueError(f"No files found in s3://{bucket}/orders/")

        latest = max(c["LastModified"] for c in contents)
        context["task_instance"].xcom_push(key="latest_file_time", value=str(latest))
        context["task_instance"].xcom_push(key="file_count", value=len(contents))

        print(f"Found {len(contents)} files in Bronze. Latest: {latest}")

    pre_check = PythonOperator(
        task_id="check_bronze_data_available",
        python_callable=check_bronze_data,
        doc="Verify Bronze data exists before Spark submit",
    )

    # -------------------------------------------------------------------------
    # Spark Submit: Bronze → Silver
    # -------------------------------------------------------------------------

    spark_submit = SparkSubmitOperator(
        task_id="spark_bronze_to_silver",
        application="s3a://aion-artifacts/spark/jobs/bronze_to_silver.py",
        conn_id="spark_default",
        name="aion-bronze-to-silver-{{ ds_nodash }}",
        application_args=[],
        env_vars={
            "BRONZE_BUCKET": "aion-bronze-raw",
            "SILVER_BUCKET": "aion-silver-lakehouse",
            "SILVER_TABLE": "orders_cleansed",
            "AWS_REGION": "eu-west-1",
            "STRICT_VALIDATION": "true",
        },
        conf=SPARK_CONFIG["conf"],
        total_executor_cores=SPARK_CONFIG["total-executor-cores"],
        executor_cores=SPARK_CONFIG["executor-cores"],
        executor_memory=SPARK_CONFIG["executor-memory"],
        driver_memory=SPARK_CONFIG["driver-memory"],
        packages=SPARK_PACKAGES,
        verbose=True,
    )

    # -------------------------------------------------------------------------
    # Post-check: verify Silver table has new data
    # -------------------------------------------------------------------------

    def verify_silver_output(**context):
        """Verify Iceberg Silver table received new records."""
        import boto3

        s3 = boto3.client("s3")
        bucket = "aion-silver-lakehouse"

        # Check that Iceberg metadata was written
        response = s3.list_objects_v2(
            Bucket=bucket, Prefix="orders/metadata/", MaxKeys=5
        )
        metadata_files = response.get("Contents", [])

        if not metadata_files:
            raise ValueError("No Iceberg metadata found — write may have failed")

        latest = max(c["LastModified"] for c in metadata_files)
        context["task_instance"].xcom_push(key="latest_metadata_time", str(latest))
        print(f"Latest Iceberg metadata: {latest}")

    post_check = PythonOperator(
        task_id="verify_silver_output",
        python_callable=verify_silver_output,
        doc="Verify Iceberg table updated",
    )

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------

    notify_success = EmailOperator(
        task_id="notify_success",
        to=["aion-data-team@example.com"],
        subject="AION Pipeline Success: Bronze → Silver {{ ds }}",
        html_content="""
        <h3>Pipeline Completed Successfully</h3>
        <table>
            <tr><td>DAG</td><td>aion_bronze_to_silver_orders</td></tr>
            <tr><td>Execution Date</td><td>{{ ds }}</td></tr>
            <tr><td>Run ID</td><td>{{ run_id }}</td></tr>
        </table>
        """,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    notify_failure = EmailOperator(
        task_id="notify_failure",
        to=["aion-alerts@example.com"],
        subject="AION Pipeline FAILED: Bronze → Silver {{ ds }}",
        html_content="""
        <h3 style="color: red;">Pipeline Failed</h3>
        <table>
            <tr><td>DAG</td><td>aion_bronze_to_silver_orders</td></tr>
            <tr><td>Execution Date</td><td>{{ ds }}</td></tr>
            <tr><td>Run ID</td><td>{{ run_id }}</td></tr>
            <tr><td>Log URL</td><td>{{ ti.log_url }}</td></tr>
        </table>
        """,
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    # -------------------------------------------------------------------------
    # Task Dependencies
    # -------------------------------------------------------------------------

    pre_check >> spark_submit >> post_check

    # Fan-out notifications (success and failure paths)
    post_check >> notify_success
    spark_submit >> notify_failure
