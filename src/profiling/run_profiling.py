#!/usr/bin/env python3
"""
run_profiling.py — execute the profiling specification (docs/profiling/data-profiling-spec.md).

Produces the six profile_* tables (spec §29) and fills docs/profiling/profiling-report.md.

Two rules this engine follows without exception:

  It classifies; it never cleans. No row is dropped, corrected or excluded. An outlier is not
  automatically a bad record (spec §2) — a very long trip, a very slow trip and a zero-distance
  trip can all be real, and deciding is a human's job with this evidence in hand.

  It proposes thresholds; it never sets one. The recommendations section carries percentiles,
  affected-record counts and two or three candidates each. configs/kpi_config.yml is not touched.

Where it reads from, and why:
  Schema, completeness, uniqueness and domain profiling read bronze_trips — the raw landing
  table — because that is what those checks are about.
  Distribution, geographic, duration and speed profiling read silver_typed, which applies
  typing and derivations but no filtering and no thresholds. Reusing it avoids a second copy of
  the Haversine formula, and a duplicated derivation is one that eventually disagrees with itself.

    python -m src.profiling.run_profiling --local
    python -m src.profiling.run_profiling --catalog nyc_taxi --schema nyc_taxi_dev
"""

import argparse
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

def _repo_root() -> Path:
    """Repo root, whether run as a script or by a Databricks serverless task.

    A serverless `spark_python_task` exec's the compiled file instead of importing it, so
    `__file__` is undefined and a plain Path(__file__) raises NameError before main() is ever
    reached. The compiled code object still carries the path, which locates the root the same
    way in both environments.
    """
    path = globals().get("__file__") or inspect.currentframe().f_code.co_filename
    return Path(path).resolve().parents[2]


ROOT = _repo_root()
if str(ROOT) not in sys.path:
    # `python -m src.profiling.run_profiling` puts the repo root on sys.path; a Databricks
    # serverless task exec's this file directly and does not, so the late
    # `from src.profiling.report import render` below would fail with ModuleNotFoundError.
    sys.path.insert(0, str(ROOT))
REPORT = ROOT / "docs" / "profiling" / "profiling-report.md"

# (value, column alias). Explicit rather than derived: str(0.50) is '0.5', so deriving the
# name from the float silently produces p5 where p50 is meant.
PCTS = [(0.25, "p25"), (0.50, "p50"), (0.75, "p75"), (0.90, "p90"),
        (0.95, "p95"), (0.99, "p99"), (0.995, "p995"), (0.999, "p999")]


def get_spark(local, warehouse):
    from pyspark.sql import SparkSession
    b = SparkSession.builder.appName("nyc-taxi-profiling")
    if local:
        b = (b.master("local[*]").config("spark.sql.warehouse.dir", warehouse)
              .config("spark.ui.enabled", "false")
              .config("spark.ui.showConsoleProgress", "false")
              .config("spark.sql.shuffle.partitions", "8").enableHiveSupport())
    s = b.getOrCreate()
    try:
        s.sparkContext.setLogLevel("ERROR")
    except Exception:
        # Databricks serverless talks Spark Connect, which deliberately does not expose
        # SparkContext. Quieting the logs is cosmetic, so it must not fail an ingestion.
        pass
    return s


def pct_expr(col):
    """Percentile expressions for one numeric column, aliased p25 … p999."""
    return ", ".join(
        f"percentile_cont({v}) WITHIN GROUP (ORDER BY {col}) AS {a}" for v, a in PCTS)


def fmt(v, nd=4):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.{nd}f}".rstrip("0").rstrip(".") if abs(v) < 1e9 else f"{v:.4g}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def secs(v):
    return "—" if v is None else f"{float(v):,.0f}s ({float(v)/60:,.1f} min)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the profiling specification.")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--warehouse", default="spark-warehouse")
    ap.add_argument("--catalog", default=None)
    ap.add_argument("--schema", default="nyc_taxi_dev",
                    help="default schema for every table below")
    ap.add_argument("--bronze", default="bronze_trips")
    ap.add_argument("--typed", default="silver_typed")
    # With one schema per medallion layer, Bronze, Silver and the profiling output do not share
    # a namespace. Each defaults to --schema, so the single-schema local run is unaffected.
    ap.add_argument("--bronze-schema", default=None, help="schema holding --bronze")
    ap.add_argument("--typed-schema", default=None, help="schema holding --typed")
    ap.add_argument("--output-schema", default=None, help="schema to write profile_* into")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--write-tables", action="store_true",
                    help="persist the six profile_* tables (spec §29)")
    a = ap.parse_args()

    spark = get_spark(a.local, a.warehouse)
    def ns_for(schema):
        return schema if (a.local or not a.catalog) else f"{a.catalog}.{schema}"

    ns = ns_for(a.output_schema or a.schema)
    bronze = f"{ns_for(a.bronze_schema or a.schema)}.{a.bronze}"
    typed = f"{ns_for(a.typed_schema or a.schema)}.{a.typed}"

    for t in (bronze, typed):
        if not spark.catalog.tableExists(t):
            print(f"run_profiling: {t} not found. Run ingestion and "
                  f"`dbt run --select silver_typed` first.", file=sys.stderr)
            return 2

    run_id = "PROFILE_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    q = spark.sql
    R = {}

    # ---- Phase 1-2: file/run metadata + schema (spec §5-6) ------------------
    meta = q(f"""SELECT COUNT(*) n, COUNT(DISTINCT source_hash) hashes,
                        MIN(source_file) f, MIN(source_hash) h, MIN(ingested_at) ing
                 FROM {bronze}""").collect()[0]
    R["run"] = dict(profiling_run_id=run_id, source_file=meta.f, source_hash=meta.h,
                    profiling_timestamp=datetime.now(timezone.utc).isoformat(),
                    row_count=meta.n, column_count=len(spark.table(bronze).columns),
                    batches=meta.hashes)

    src_cols = [c for c in spark.table(bronze).columns
                if c not in ("source_file", "source_hash", "ingested_at")]

    # ---- Phase 3: completeness (spec §7) ------------------------------------
    nulls = q("SELECT " + ", ".join(
        f"SUM(CASE WHEN {c} IS NULL OR TRIM({c})='' THEN 1 ELSE 0 END) AS {c}"
        for c in src_cols) + f" FROM {bronze}").collect()[0].asDict()
    R["completeness"] = [(c, nulls[c], 100.0 * nulls[c] / meta.n) for c in src_cols]

    # ---- Phase 4: uniqueness / duplicates (spec §8, §26) --------------------
    dup = q(f"""
        WITH k AS (SELECT id, COUNT(*) n FROM {bronze} WHERE id IS NOT NULL AND TRIM(id)<>''
                   GROUP BY id)
        SELECT (SELECT COUNT(*) FROM k) distinct_ids,
               (SELECT COUNT(*) FROM k WHERE n>1) duplicated_ids,
               (SELECT COALESCE(SUM(n),0) FROM k WHERE n>1) duplicate_rows""").collect()[0]
    exact = q(f"""SELECT COALESCE(SUM(n),0) c FROM (
        SELECT COUNT(*) n FROM {bronze}
        GROUP BY {', '.join(src_cols)} HAVING COUNT(*)>1)""").collect()[0].c
    R["uniqueness"] = dict(distinct_ids=dup.distinct_ids, duplicated_ids=dup.duplicated_ids,
                           duplicate_rows=dup.duplicate_rows, exact_duplicate_rows=exact,
                           duplicate_rate=100.0 * dup.duplicate_rows / meta.n)

    # ---- Phase 5: domains (spec §9) -----------------------------------------
    R["domains"] = {}
    for col in ("vendor_id", "store_and_fwd_flag", "passenger_count"):
        R["domains"][col] = [
            (r[col], r.n, 100.0 * r.n / meta.n)
            for r in q(f"SELECT {col}, COUNT(*) n FROM {bronze} GROUP BY {col} "
                       f"ORDER BY n DESC LIMIT 25").collect()]

    # ---- Phase 6: temporal + duration consistency (spec §10-11) -------------
    R["temporal"] = q(f"""SELECT MIN(pickup_date) min_date, MAX(pickup_date) max_date,
        COUNT(DISTINCT pickup_date) days,
        SUM(CASE WHEN duration_difference_seconds=0 THEN 1 ELSE 0 END) exact_match,
        SUM(CASE WHEN duration_difference_seconds<>0 THEN 1 ELSE 0 END) mismatch,
        MIN(duration_difference_seconds) min_diff, MAX(duration_difference_seconds) max_diff,
        AVG(duration_difference_seconds) mean_diff,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_difference_seconds) median_diff
        FROM {typed}""").collect()[0].asDict()
    R["by_hour"] = [(r.pickup_hour, r.n) for r in
                    q(f"SELECT pickup_hour, COUNT(*) n FROM {typed} GROUP BY pickup_hour "
                      f"ORDER BY pickup_hour").collect()]
    R["by_dow"] = [(r.day_of_week, r.n) for r in
                   q(f"SELECT day_of_week, COUNT(*) n FROM {typed} GROUP BY day_of_week "
                     f"ORDER BY n DESC").collect()]

    # ---- Phase 7: geography (spec §14-16) -----------------------------------
    R["geo"] = q(f"""SELECT
        MIN(pickup_latitude) plat_min, MAX(pickup_latitude) plat_max,
        MIN(pickup_longitude) plon_min, MAX(pickup_longitude) plon_max,
        percentile_cont(0.01) WITHIN GROUP (ORDER BY pickup_latitude) plat_p1,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY pickup_latitude) plat_p99,
        percentile_cont(0.01) WITHIN GROUP (ORDER BY pickup_longitude) plon_p1,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY pickup_longitude) plon_p99,
        SUM(CASE WHEN pickup_latitude IS NULL OR pickup_longitude IS NULL
                   OR dropoff_latitude IS NULL OR dropoff_longitude IS NULL
                 THEN 1 ELSE 0 END) geo_001,
        SUM(CASE WHEN ABS(pickup_latitude)>90 OR ABS(dropoff_latitude)>90 THEN 1 ELSE 0 END) geo_002,
        SUM(CASE WHEN ABS(pickup_longitude)>180 OR ABS(dropoff_longitude)>180 THEN 1 ELSE 0 END) geo_003,
        SUM(CASE WHEN pickup_latitude=0 AND pickup_longitude=0 THEN 1 ELSE 0 END) geo_at_origin,
        SUM(CASE WHEN pickup_latitude=dropoff_latitude
                  AND pickup_longitude=dropoff_longitude THEN 1 ELSE 0 END) geo_005
        FROM {typed}""").collect()[0].asDict()

    # ---- Phase 8-9: duration, distance, speed (spec §17-22) -----------------
    for name, col, extra in (("duration", "trip_duration", ""),
                             ("distance", "estimated_distance_km", ""),
                             ("speed", "estimated_speed_kmh", "")):
        R[name] = q(f"""SELECT COUNT({col}) n, MIN({col}) min, MAX({col}) max,
            AVG({col}) mean, STDDEV({col}) stddev, {pct_expr(col)}
            FROM {typed} WHERE {col} IS NOT NULL {extra}""").collect()[0].asDict()

    R["duration_extras"] = q(f"""SELECT
        SUM(CASE WHEN trip_duration=0 THEN 1 ELSE 0 END) zero,
        SUM(CASE WHEN trip_duration<0 THEN 1 ELSE 0 END) negative,
        SUM(CASE WHEN trip_duration IS NULL THEN 1 ELSE 0 END) null_count
        FROM {typed}""").collect()[0].asDict()
    R["distance_extras"] = q(f"""SELECT
        SUM(CASE WHEN estimated_distance_km=0 THEN 1 ELSE 0 END) zero_distance
        FROM {typed}""").collect()[0].asDict()
    # IQR bound, spec §19 Method B
    d = R["duration"]
    iqr = (d["p75"] - d["p25"]) if d["p75"] is not None else None
    R["duration_iqr"] = dict(iqr=iqr, upper=(d["p75"] + 1.5 * iqr) if iqr is not None else None)

    # ---- Phase 10-11: vendor + store-and-forward (spec §24-25) -------------
    R["vendor"] = [r.asDict() for r in q(f"""SELECT vendor_id, COUNT(*) n,
        AVG(trip_duration) avg_dur,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY trip_duration) p50,
        percentile_cont(0.9) WITHIN GROUP (ORDER BY trip_duration) p90,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY trip_duration) p95,
        AVG(estimated_distance_km) avg_dist, AVG(estimated_speed_kmh) avg_speed
        FROM {typed} GROUP BY vendor_id ORDER BY vendor_id""").collect()]
    R["saf"] = [r.asDict() for r in q(f"""SELECT store_and_fwd_flag_raw flag, COUNT(*) n,
        AVG(trip_duration) avg_dur,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY trip_duration) p50,
        percentile_cont(0.9) WITHIN GROUP (ORDER BY trip_duration) p90
        FROM {typed} GROUP BY store_and_fwd_flag_raw ORDER BY n DESC""").collect()]

    # ---- Phase 12: DQ rule evaluation -> profile_quality --------------------
    import yaml
    rules = yaml.safe_load((ROOT / "configs" / "quality_rules.yml").read_text())["rules"]
    R["dq"] = []
    for r in rules:
        rid = r["id"]
        if r["action"] == "policy":
            R["dq"].append((rid, r["name"], None, None, "POLICY"))
            continue
        if r.get("value") == "TBD_PENDING_PROFILING":
            R["dq"].append((rid, r["name"], None, None, "BLOCKED_PENDING_THRESHOLD"))
            continue
        preds = {
            "DQ-001": "id IS NULL", "DQ-004": "pickup_datetime IS NULL",
            "DQ-005": "dropoff_datetime IS NULL",
            "DQ-006": "dropoff_datetime < pickup_datetime",
            "DQ-007": "trip_duration IS NULL OR trip_duration <= 0",
            "DQ-011": "store_and_fwd_flag_original NOT IN ('Y','N')",
            "DQ-012": "estimated_distance_km < 0", "DQ-013": "estimated_speed_kmh < 0",
        }
        if rid not in preds:
            R["dq"].append((rid, r["name"], None, None, "NOT_EVALUATED"))
            continue
        failed = q(f"SELECT COUNT(*) c FROM {typed} WHERE {preds[rid]}").collect()[0].c
        R["dq"].append((rid, r["name"], failed, 100.0 * failed / meta.n,
                        "PASS" if failed == 0 else "FAIL"))

    R["dq_002"] = dup.duplicate_rows

    # ---- write profile_* tables (spec §29) ----------------------------------
    if a.write_tables:
        from pyspark.sql import Row
        def save(name, rows):
            if rows:
                spark.createDataFrame(rows).write.mode("overwrite").saveAsTable(f"{ns}.{name}")
        save("profile_run", [Row(**R["run"])])
        save("profile_schema", [Row(profiling_run_id=run_id, column_name=c,
                                    null_count=int(n), null_rate=float(p))
                                for c, n, p in R["completeness"]])
        save("profile_numeric_stats", [Row(profiling_run_id=run_id, column_name=k,
                                           **{kk: (float(vv) if vv is not None else None)
                                              for kk, vv in R[k].items()})
                                       for k in ("duration", "distance", "speed")])
        save("profile_domain_stats", [Row(profiling_run_id=run_id, column_name=col,
                                          value=str(v), count=int(n), percentage=float(p))
                                      for col, vals in R["domains"].items() for v, n, p in vals])
        save("profile_quality", [Row(profiling_run_id=run_id, rule_id=rid, rule_name=nm,
                                     total_records=int(meta.n),
                                     failed_records=(int(f) if f is not None else None),
                                     failure_rate=(float(fr) if fr is not None else None),
                                     status=st)
                                 for rid, nm, f, fr, st in R["dq"]])
        save("profile_anomalies", [Row(profiling_run_id=run_id, anomaly_type=k,
                                       record_count=int(v),
                                       percentage=float(100.0 * v / meta.n))
                                   for k, v in (("GEO-001", R["geo"]["geo_001"]),
                                                ("GEO-002", R["geo"]["geo_002"]),
                                                ("GEO-003", R["geo"]["geo_003"]),
                                                ("GEO-005", R["geo"]["geo_005"]),
                                                ("ZERO_DURATION", R["duration_extras"]["zero"]),
                                                ("NEGATIVE_DURATION", R["duration_extras"]["negative"]),
                                                ("ZERO_DISTANCE", R["distance_extras"]["zero_distance"]))])
        print(f"wrote 6 profile_* tables to {ns}")

    from src.profiling.report import render
    REPORT_PATH = Path(a.report)
    REPORT_PATH.write_text(render(R, PCTS), encoding="utf-8")
    print(f"run_profiling: {run_id}")
    print(f"  rows={meta.n:,}  columns={R['run']['column_count']}  batches={meta.hashes}")
    print(f"  report -> {REPORT_PATH}")
    print("\nNext: review the threshold recommendations, then use the threshold-decision skill.")
    print("This engine proposes candidates; approving one is a human decision.")
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
