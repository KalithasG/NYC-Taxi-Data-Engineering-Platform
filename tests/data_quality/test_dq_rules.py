"""
Per-rule tests for DQ-001..DQ-015 (configs/quality_rules.yml).

Each rule gets three things, which together are what "implemented" means for a DQ rule:
  1. a row that passes the predicate,
  2. a row that fails it, asserted to land where the rule's action says it should —
     quarantine with the right reason for `reject`, a flag column for `flag`,
  3. the reconciliation total = valid + quarantined, which is the check that catches rows
     disappearing between the two.

Thresholds and domains are read from configs/quality_rules.yml at runtime. Hard-coding a bound
into a test duplicates the contract, and the copy drifts.

Run after building the pipeline:
    python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
    python -m src.transformations.run --target local --allow-withheld
    pytest tests/data_quality
"""

from pathlib import Path

import pytest

pyspark = pytest.importorskip("pyspark", reason="local Spark verification harness")
yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
RULES = yaml.safe_load((ROOT / "configs" / "quality_rules.yml").read_text())["rules"]
BY_ID = {r["id"]: r for r in RULES}
SENTINEL = "TBD_PENDING_PROFILING"

# Rules whose failing rows the fixture plants, with the count it plants.
PLANTED_REJECTS = {"DQ-001": 3, "DQ-004": 2, "DQ-005": 2, "DQ-006": 4, "DQ-007": 5, "DQ-009": 5}
PLANTED_FLAGS = {"DQ-008": ("is_passenger_count_anomaly", 5),
                 "DQ-011": ("is_store_fwd_flag_anomaly", 3)}


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


def scalar(spark, sql):
    return spark.sql(sql).collect()[0][0]


# ---------------------------------------------------------------- contract shape
@pytest.mark.parametrize("rid", sorted(BY_ID))
def test_rule_is_structurally_complete(rid):
    """A reject rule without a quarantine_reason is unauditable (DQ-015); a flag rule
    without a flag_column has nowhere to put the flag."""
    r = BY_ID[rid]
    assert r.get("name") and r.get("type") and r.get("action")
    if r["action"] == "reject":
        assert r.get("quarantine_reason"), f"{rid} rejects rows but records no reason"
        assert r.get("predicate")
    elif r["action"] == "flag":
        assert r.get("flag_column"), f"{rid} flags rows but names no column"
        assert r.get("predicate")
    else:
        assert r.get("enforces"), f"{rid} is a policy but does not say what it enforces"


# ---------------------------------------------------------------- reject rules
@pytest.mark.parametrize("rid,expected", sorted(PLANTED_REJECTS.items()))
def test_reject_rule_quarantines_failing_rows(spark, rid, expected):
    n = scalar(spark, f"SELECT COUNT(*) FROM silver_trips_quarantine WHERE rule_id='{rid}'")
    assert n == expected, f"{rid}: fixture plants {expected} failing rows, quarantined {n}"


@pytest.mark.parametrize("rid", sorted(PLANTED_REJECTS))
def test_quarantined_rows_carry_the_contracted_reason(spark, rid):
    want = BY_ID[rid]["quarantine_reason"]
    got = {r[0] for r in spark.sql(
        f"SELECT DISTINCT quarantine_reason FROM silver_trips_quarantine "
        f"WHERE rule_id='{rid}'").collect()}
    assert got == {want}, f"{rid}: expected reason {want!r}, found {got}"


@pytest.mark.parametrize("rid", sorted(PLANTED_REJECTS))
def test_rejected_rows_are_absent_from_the_valid_population(spark, rid):
    """A rejected row must not also appear in silver_trips — that would double-count it."""
    n = scalar(spark, f"""SELECT COUNT(*) FROM silver_trips t
        JOIN silver_trips_quarantine q ON q.id = t.id AND q.rule_id = '{rid}'""")
    assert n == 0


# ---------------------------------------------------------------- flag rules
@pytest.mark.parametrize("rid", sorted(PLANTED_FLAGS))
def test_flag_rule_keeps_the_row(spark, rid):
    """DQ-014 and profiling §2: a flag marks a row, it never removes one."""
    col, expected = PLANTED_FLAGS[rid]
    assert BY_ID[rid]["action"] == "flag"
    assert BY_ID[rid]["flag_column"] == col
    n = scalar(spark, f"SELECT COUNT(*) FROM silver_trips WHERE {col}")
    assert n == expected, f"{rid}: expected {expected} flagged rows in the valid population, got {n}"
    quarantined = scalar(spark,
                         f"SELECT COUNT(*) FROM silver_trips_quarantine WHERE rule_id='{rid}'")
    assert quarantined == 0, f"{rid} is a flag rule and must never quarantine"


def test_dq_011_is_evaluated_before_normalisation(spark):
    """The planted lowercase 'y' must be flagged. Normalising to upper case before validating
    would turn it into a valid 'Y' and erase the evidence that the source emits mixed casing
    (profiling §9.2). This test exists because that bug was real."""
    assert scalar(spark, "SELECT COUNT(*) FROM silver_trips WHERE is_store_fwd_flag_anomaly") == 3


# ---------------------------------------------------------------- derived validity
@pytest.mark.parametrize("rid,col", [("DQ-012", "estimated_distance_km"),
                                     ("DQ-013", "estimated_speed_kmh")])
def test_derived_values_are_non_negative(spark, rid, col):
    """A negative Haversine distance or speed indicates a defect in the transformation, not bad
    source data — a hit here is a bug report against the pipeline."""
    assert scalar(spark, f"SELECT COUNT(*) FROM silver_trips WHERE {col} < 0") == 0


# ---------------------------------------------------------------- policies
def test_dq_014_outliers_are_flagged_never_deleted(spark):
    """The fixture plants two 20-hour trips. They must survive into the valid population and
    count toward KPI-001."""
    n = scalar(spark, "SELECT COUNT(*) FROM silver_trips WHERE trip_duration >= 72000")
    assert n == 2, "extreme-duration trips must be retained, not removed"


def test_dq_015_every_rejection_is_auditable(spark):
    missing = scalar(spark, """SELECT COUNT(*) FROM silver_trips_quarantine
                               WHERE rule_id IS NULL OR quarantine_reason IS NULL""")
    assert missing == 0


def test_dq_015_reconciliation(spark):
    r = spark.sql("""SELECT total_records, valid_records, quarantined_records
                     FROM gold.data_quality""").collect()[0]
    assert r.total_records == r.valid_records + r.quarantined_records, "silent data loss"


# ---------------------------------------------------------------- parameter governance
# DQ-008, DQ-009 and DQ-010 were approved on 2026-08-29 from profiling evidence, which is the
# revisit this test asked for when it covered all four. DQ-003 is the one still pending: it
# rejects, so an unreviewed vendor domain would quarantine real rows.
@pytest.mark.parametrize("rid", ["DQ-003"])
def test_pending_parameters_are_still_sentinels(rid):
    """Still waiting on an approval. If one acquires a value without a decision record,
    check_thresholds.py blocks the commit."""
    assert BY_ID[rid].get("value") == SENTINEL, (
        f"{rid} now has a value — re-check the partial-enforcement assumptions in "
        f"silver_dq_evaluated.sql and update these tests")


@pytest.mark.parametrize("rid", ["DQ-008", "DQ-009", "DQ-010"])
def test_approved_parameters_have_a_value_and_a_decision_record(rid):
    """A resolved parameter is only legitimate with a recorded decision behind it. Asserting the
    value alone would let a number appear with nobody's name on it, which is the failure the
    whole threshold-governance design exists to prevent."""
    rule = BY_ID[rid]
    value = rule.get("value")
    assert value != SENTINEL, f"{rid} lost its approved value"
    assert value not in (None, ""), f"{rid} has an empty value"

    decisions = (ROOT / "docs" / "profiling" / "threshold-decisions.md").read_text(
        encoding="utf-8")
    param = rule.get("parameter")
    assert param and param in decisions, (
        f"{rid}.{param} has a value but no decision record in threshold-decisions.md")
    section = decisions[decisions.index(param):]
    for field in ("Approved by", "Evidence", "Records affected", "Alternatives"):
        assert field.lower() in section.lower()[:4000], (
            f"the {param} decision record is missing '{field}'")


def test_geo_005_is_classified_not_rejected(spark):
    """pickup == dropoff is a classification, not a rejection (profiling §15). A zero-distance
    trip can be real."""
    kept = scalar(spark, "SELECT COUNT(*) FROM silver_trips WHERE coordinate_anomaly='GEO-005'")
    assert kept == 4


# ---------------------------------------------------------------- DQ-002 duplicates
# Duplicate handling is the subtlest rule in the contract, so it gets its own block. The
# fixture plants one id four times: the original, two exact copies (type A/B) and one row with
# a conflicting payload (type C).

def test_dq_002_quarantines_every_row_of_a_duplicated_id(spark):
    n = scalar(spark, "SELECT COUNT(*) FROM silver_trips_quarantine WHERE rule_id='DQ-002'")
    assert n == 4, ("all rows sharing a duplicated id go to quarantine — keeping one and "
                    "dropping the rest would silently pick a winner between conflicting payloads")


def test_dq_002_reason_matches_the_contract(spark):
    got = {r[0] for r in spark.sql("SELECT DISTINCT quarantine_reason FROM "
                                   "silver_trips_quarantine WHERE rule_id='DQ-002'").collect()}
    assert got == {BY_ID["DQ-002"]["quarantine_reason"]}


def test_dq_002_valid_population_has_unique_ids(spark):
    dupes = scalar(spark, """SELECT COUNT(*) FROM
        (SELECT id FROM silver_trips GROUP BY id HAVING COUNT(*) > 1)""")
    assert dupes == 0


def test_dq_002_kpi_020_reads_the_pre_deduplication_count(spark):
    """KPI-020 must count duplicates from the original population. Reading the deduplicated
    Silver table would report zero forever and make a dirty batch look clean (contract §11)."""
    r = spark.sql("SELECT duplicate_records, total_records FROM gold.data_quality").collect()[0]
    assert r.duplicate_records == 4
    assert scalar(spark, "SELECT COUNT(*) FROM silver_trips") < r.total_records, (
        "Silver is deduplicated, so it is smaller than the source batch — which is exactly why "
        "KPI-020 cannot be computed from it")


def test_dq_002_null_ids_are_not_counted_as_duplicates(spark):
    """Spark groups NULLs together in a window partition, so without an explicit guard every
    null-id row counts as a duplicate of every other. A missing primary key is DQ-001. This
    test exists because that bug was real."""
    null_ids = scalar(spark, "SELECT COUNT(*) FROM silver_trips_quarantine WHERE rule_id='DQ-001'")
    dup_count = scalar(spark, "SELECT duplicate_records FROM gold.data_quality")
    assert null_ids == 3 and dup_count == 4, (
        "3 null-id rows and 4 duplicate rows must be counted under different rules")
