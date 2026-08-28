#!/usr/bin/env python3
"""
load_bronze.py — land the source CSV in Bronze, immutably and idempotently.

Bronze is append-only. Every row carries source_file, source_hash and ingested_at, and
re-running with a file whose hash is already present adds nothing (BDD-01). That is what makes
the job safe to retry and every downstream number traceable to an exact input.

A correction is a new ingestion, never an edit to a landed row.

Local:       python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
Databricks:  run as a Job task; --input points at a Unity Catalog volume path.
"""

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_DDL = (
    "id STRING, vendor_id STRING, pickup_datetime STRING, dropoff_datetime STRING, "
    "passenger_count STRING, pickup_longitude STRING, pickup_latitude STRING, "
    "dropoff_longitude STRING, dropoff_latitude STRING, store_and_fwd_flag STRING, "
    "trip_duration STRING"
)
# Read every column as STRING. Casting happens in Silver, where a failed cast becomes a
# recorded DQ failure rather than a row Spark silently nulls out during ingestion.


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_spark(local: bool, warehouse: str):
    from pyspark.sql import SparkSession
    b = SparkSession.builder.appName("nyc-taxi-bronze")
    if local:
        # Delta configs come from SPARK_CONF_DIR (conf/spark-defaults.conf) so ingestion, dbt,
        # profiling and pytest all share one definition instead of four drifting copies.
        b = (b.master("local[*]")
              .config("spark.sql.warehouse.dir", warehouse)
              .config("spark.ui.enabled", "false")
              .config("spark.ui.showConsoleProgress", "false")
              .enableHiveSupport())
    s = b.getOrCreate()
    try:
        s.sparkContext.setLogLevel("ERROR")
    except Exception:
        # Databricks serverless talks Spark Connect, which deliberately does not expose
        # SparkContext. Quieting the logs is cosmetic, so it must not fail an ingestion.
        pass
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description="Land the source CSV in Bronze.")
    ap.add_argument("--input", required=True, help="CSV path (local file or UC volume path)")
    ap.add_argument("--catalog", default=None, help="Unity Catalog name (omit when --local)")
    ap.add_argument("--schema", default="nyc_taxi_dev")
    ap.add_argument("--table", default="bronze_trips")
    ap.add_argument("--local", action="store_true", help="local Spark session, no Unity Catalog")
    ap.add_argument("--warehouse", default="spark-warehouse", help="local warehouse dir")
    ap.add_argument("--force", action="store_true",
                    help="re-land a hash that is already present (creates duplicates — "
                         "only for a deliberate replay)")
    a = ap.parse_args()

    src = Path(a.input)
    if not src.exists() and a.local:
        print(f"load_bronze: {src} not found", file=sys.stderr)
        return 2

    digest = sha256_of(src) if a.local else None
    spark = get_spark(a.local, a.warehouse)

    fq = f"{a.schema}.{a.table}" if a.local or not a.catalog else f"{a.catalog}.{a.schema}.{a.table}"
    if a.local:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {a.schema}")
    else:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {a.catalog}.{a.schema}")
        digest = digest or sha256_of(src)

    df = (spark.read.option("header", True).schema(SCHEMA_DDL).csv(str(src)))

    from pyspark.sql import functions as F
    df = (df.withColumn("source_file", F.lit(src.name))
            .withColumn("source_hash", F.lit(digest))
            .withColumn("ingested_at", F.lit(datetime.now(timezone.utc).isoformat())))

    exists = spark.catalog.tableExists(fq)
    if exists and not a.force:
        already = (spark.table(fq).where(F.col("source_hash") == digest).limit(1).count())
        if already:
            n = spark.table(fq).count()
            print(f"load_bronze: source_hash {digest[:16]}… already present in {fq}; "
                  f"nothing appended (idempotent). Bronze holds {n} rows.")
            spark.stop()
            return 0

    # Delta in both places. Locally that needs SPARK_CONF_DIR=./conf (see conf/spark-defaults.conf);
    # without it the write fails loudly rather than silently falling back to Parquet, because a
    # local format that differs from production means the thing verified is not the thing that runs.
    (df.write.mode("append" if exists else "overwrite").format("delta").saveAsTable(fq))

    n = spark.table(fq).count()
    print(f"load_bronze: appended {df.count()} rows to {fq} "
          f"(source_hash {digest[:16]}…). Bronze now holds {n} rows.")

    # Delta's commit log is the append-only audit trail Pillar 7 relies on. Note there is
    # deliberately no MERGE here: MERGE updates rows in place, and Bronze is immutable. The
    # idempotency guarantee comes from the source_hash check above, not from overwriting.
    try:
        hist = spark.sql(f"DESCRIBE HISTORY {fq}").collect()
        print(f"            Delta history: {len(hist)} commit(s); latest "
              f"{hist[0].operation} at {hist[0].timestamp}")
    except Exception:
        pass  # DESCRIBE HISTORY is reporting, not a precondition

    spark.stop()
    return 0


if __name__ == "__main__":
    # Exit non-zero only on failure. A Databricks serverless task runs this file inside an
    # IPython kernel, which reports any SystemExit — including SystemExit(0) — as a failed
    # task. Returning normally on success keeps the exit codes identical on a terminal while
    # letting the task succeed. A non-zero code still raises, which is what fails the gate.
    _rc = main()
    if _rc:
        sys.exit(_rc)
