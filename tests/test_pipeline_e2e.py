"""
End-to-end pipeline assertions against the synthetic fixture.

Every number here was produced by an actual run, not predicted. The fixture plants a known set
of defects (tests/fixtures/make_fixture.py) and these lock in what the pipeline must do with
each one — so a future change that quietly starts dropping rows, normalising away an anomaly,
or double-counting on rerun fails here rather than in a dashboard.

Run:
    python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
    python -m src.transformations.run --target local --allow-withheld
    pytest tests/test_pipeline_e2e.py
"""

import pytest

pyspark = pytest.importorskip("pyspark", reason="local Spark verification harness")

FIXTURE_TOTAL = 441
FIXTURE_VALID = 416
FIXTURE_QUARANTINED = 25
FIXTURE_DUPLICATES = 4          # id0000000 x4; null ids are DQ-001, NOT duplicates

# rule -> rows the fixture plants for it
QUARANTINE_BY_RULE = {
    "DQ-001": 3,   # null id
    "DQ-002": 4,   # 1 original + 2 exact copies + 1 conflicting payload
    "DQ-004": 2,   # null pickup
    "DQ-005": 2,   # null dropoff
    "DQ-006": 4,   # dropoff before pickup
    "DQ-007": 5,   # 3 zero-duration + 2 negative
    "DQ-009": 5,   # 2 null coordinate + 3 at (0,0)
}


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[*]")
         .config("spark.sql.warehouse.dir", "spark-warehouse")
         .config("spark.ui.enabled", "false")
         .config("spark.ui.showConsoleProgress", "false")
         .enableHiveSupport().getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    s.sql("USE nyc_taxi_dev")
    yield s
    s.stop()


def one(spark, sql):
    return spark.sql(sql).collect()[0]


# ---------- BDD-02 / DQ-015: no silent data loss ----------
def test_reconciliation_holds(spark):
    r = one(spark, "SELECT * FROM gold.data_quality")
    assert r.total_records == FIXTURE_TOTAL
    assert r.valid_records == FIXTURE_VALID
    assert r.quarantined_records == FIXTURE_QUARANTINED
    assert r.total_records == r.valid_records + r.quarantined_records
    assert r.reconciles is True


def test_every_quarantined_row_has_a_reason(spark):
    n = one(spark, """SELECT COUNT(*) c FROM silver_trips_quarantine
                      WHERE rule_id IS NULL OR quarantine_reason IS NULL""").c
    assert n == 0


@pytest.mark.parametrize("rule,expected", sorted(QUARANTINE_BY_RULE.items()))
def test_quarantine_counts_match_planted_defects(spark, rule, expected):
    n = one(spark, f"SELECT COUNT(*) c FROM silver_trips_quarantine WHERE rule_id='{rule}'").c
    assert n == expected, f"{rule}: expected {expected} planted rows, quarantined {n}"


# ---------- BDD-03 / DQ-014: flagged, never deleted ----------
def test_flagged_rows_stay_in_the_valid_population(spark):
    r = one(spark, """SELECT
        SUM(CASE WHEN is_passenger_count_anomaly THEN 1 ELSE 0 END) pc,
        SUM(CASE WHEN is_store_fwd_flag_anomaly  THEN 1 ELSE 0 END) sf
        FROM silver_trips""")
    assert r.pc == 5, "passenger_count=0 must be flagged, not rejected (spec OQ-5)"
    assert r.sf == 3, ("lowercase store_and_fwd must be flagged — normalising before "
                       "validating would erase the evidence (profiling §9.2)")


def test_zero_distance_trips_are_kept(spark):
    n = one(spark, "SELECT COUNT(*) c FROM silver_trips WHERE coordinate_anomaly='GEO-005'").c
    assert n == 4, "pickup == dropoff is classified, not rejected (profiling §15)"


# ---------- BDD-06 / KPI-020: duplicates counted pre-deduplication ----------
def test_duplicate_rate_reads_the_original_population(spark):
    r = one(spark, "SELECT duplicate_records, kpi_020_duplicate_rate_pct FROM gold.data_quality")
    assert r.duplicate_records == FIXTURE_DUPLICATES
    # Spark returns DECIMAL for a rounded percentage; float() keeps the comparison honest.
    assert float(r.kpi_020_duplicate_rate_pct) == pytest.approx(
        100 * FIXTURE_DUPLICATES / FIXTURE_TOTAL, abs=0.01)


def test_silver_contains_no_duplicate_ids(spark):
    n = one(spark, "SELECT COUNT(*) c FROM (SELECT id FROM silver_trips GROUP BY id HAVING COUNT(*)>1)").c
    assert n == 0


# ---------- the 20 KPIs ----------
def test_kpi_001_counts_every_valid_trip(spark):
    assert one(spark, "SELECT SUM(kpi_001_total_trips) t FROM gold.trip_performance").t == FIXTURE_VALID


def test_demand_totals_agree_with_kpi_001(spark):
    assert one(spark, "SELECT SUM(kpi_008_trips_per_hour) t FROM gold.demand_metrics").t == FIXTURE_VALID


def test_kpi_013_shares_sum_to_100(spark):
    t = one(spark, "SELECT SUM(kpi_013_vendor_trip_share_pct) t FROM gold.vendor_performance").t
    assert float(t) == pytest.approx(100.0, abs=0.01)


def test_geographic_mart_ranks_all_three_dimensions(spark):
    dims = {r.dimension for r in spark.sql(
        "SELECT DISTINCT dimension FROM gold.geographic_metrics").collect()}
    assert dims == {"pickup_area", "dropoff_area", "route"}


# ---------- BDD-05: thresholds ----------
def test_blocked_kpis_are_withheld_not_defaulted(spark):
    cols = spark.table("gold.trip_performance").columns
    assert "kpi_016_withheld_pending_long_trip_seconds" in cols
    assert "kpi_017_withheld_pending_low_speed_kmh" in cols
    assert "kpi_016_long_trip_rate_pct" not in cols, "a withheld KPI must not appear as a value"


# ---------- BDD-07: wording ----------
def test_no_column_claims_road_distance(spark):
    for t in ("silver_trips", "gold.trip_performance", "gold.geographic_metrics",
              "gold.vendor_performance"):
        for c in spark.table(t).columns:
            low = c.lower()
            assert not (("distance" in low or "speed" in low)
                        and any(w in low for w in ("actual", "road", "driving", "route_dist"))), \
                f"{t}.{c} implies a road measure; these are geodesic (BDD-07)"


# ---------- Delta ----------
# "We use Delta" is a claim until the commit log answers. These assert the two properties the
# architecture actually depends on: an append-only audit trail (Pillar 7) and a format that
# matches production, so what is verified locally is what runs on Databricks.

def test_bronze_is_delta(spark):
    fmt = [r.data_type for r in spark.sql("DESCRIBE EXTENDED bronze_trips").collect()
           if r.col_name.strip().lower() == "provider"]
    assert fmt and fmt[0].strip().lower() == "delta", (
        "Bronze must be Delta in every environment. A local Parquet fallback means the format "
        "verified here is not the format that runs.")


def test_bronze_has_a_commit_history(spark):
    hist = spark.sql("DESCRIBE HISTORY bronze_trips").collect()
    assert len(hist) >= 1, "Delta commit log is the append-only audit trail Pillar 7 relies on"
    ops = {h.operation for h in hist}
    assert not {"UPDATE", "DELETE", "MERGE"} & ops, (
        f"Bronze is append-only; found mutating operation(s) in its history: "
        f"{ {'UPDATE','DELETE','MERGE'} & ops }")
