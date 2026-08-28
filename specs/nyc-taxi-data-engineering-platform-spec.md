# Specification — NYC Taxi Data Engineering Platform

**Spec version:** 1.0
**Status:** Approved for build · thresholds pending profiling
**Tier:** structured (see `PROJECT_PLAN.md`)
**Upstream contracts:** `docs/business/kpi-data-contract.md` (KPI contract v1.0),
`docs/business/kpi-discussion.md`, `docs/profiling/data-profiling-spec.md`

> Source of truth for both humans and the coding agent. The code is disposable; this is not.
> Narrative in Markdown; deep config and schemas in YAML under `configs/`.

---

## 1. Problem & goals

**Problem.** Raw NYC taxi trip data is a flat CSV with no guarantees: unknown completeness,
unverified uniqueness, coordinates of unknown plausibility, and a `trip_duration` column whose
agreement with the pickup/drop-off timestamps has never been measured. Business questions about
demand, trip performance, geography and vendor behaviour cannot be answered from it without first
establishing what is trustworthy.

This platform converts that raw file into **trusted, queryable business metrics** through a
layered pipeline with explicit, auditable data-quality rules — so that a number on a dashboard can
be traced back to the rows that produced it.

**Goals / success criteria.**

| # | Goal | Measured by |
|---|---|---|
| G1 | All 20 business KPIs computable from the curated layer | `configs/kpi_config.yml` ids all resolve to a Gold model |
| G2 | Every KPI reproducible across reruns | Same input hash → identical Gold output (BDD-04) |
| G3 | No silent data loss | Every rejected row is retrievable from the quarantine table (BDD-02) |
| G4 | Data quality is itself a measured product | KPI-018/019/020 emitted per batch |
| G5 | Thresholds are evidence-based, never invented | No `TBD_PENDING_PROFILING` value reaches a Gold model |
| G6 | Full lineage source → Gold for every KPI | Contract §17 lineage block present per KPI |

**Non-functional targets.** Full pipeline run on the training dataset completes within the
Databricks Free Edition serverless budget; a rerun is idempotent; all transformations are
deterministic given the same input.

---

## 2. Non-goals

Explicitly out of scope — the agent must not invent these:

- **Metrics that evaluate a predictive model** (KPI-021..024 in the v1.0 contract document:
  RMSLE, MAE, RMSE, P90 Absolute Error). They measure a model, not the taxi operation — a
  different grain, lifecycle and audience. See KPI contract §12, and §9 OQ-1 for the pending
  v1.1 record of that decision.
- **Model training, hyperparameter tuning, model registry, prediction serving.**
- **Feature engineering for a model.** `src/features/` is reserved for future enrichment of the
  trip data (the extensions in contract §19); it does not build model features.
- The twelve future extensions in KPI contract §19: fare, revenue, revenue/km, driver earnings,
  customer wait time, pickup ETA accuracy, road-network distance, traffic congestion index,
  airport trip performance, weather adjustment, event adjustment, SLA compliance. Each needs a
  dataset this project does not have.
- **Road-network distance.** `estimated_distance_km` is geodesic (Haversine) and must be labelled
  as such everywhere it surfaces. See §8 Naming rules.
- Real-time / streaming ingestion. The source is a static Kaggle file; batch only.

---

## 3. Users & core flows

**Primary users**
- *Operations analyst* — reads the executive dashboard, asks when demand peaks and how long trips take.
- *Data engineer* — owns the pipeline, DQ rules and thresholds.
- *Downstream consumer* — reads the trusted Gold marts rather than re-ingesting the raw file.

**Core flows**

1. **Ingest** — acquire the Kaggle file, record its hash, land it immutably in Bronze.
2. **Profile** — run the profiling spec's 16 steps, emit `profile_*` tables and a report.
3. **Decide thresholds** — convert profiling evidence into approved thresholds; bump the contract.
4. **Curate** — apply DQ-001..015, derive the reusable fields, split valid / flagged / quarantined.
5. **Aggregate** — build the six Gold marts and compute KPI-001..020.
6. **Consume** — serve the executive dashboard from the Gold marts.

Flow 3 gates flow 5: no KPI depending on a TBD threshold can be published before its threshold is
approved (G5).

---

## 4. Architecture & key decisions

| Decision | Options considered | Choice | Rationale |
|---|---|---|---|
| Platform | Local DuckDB / PySpark+Airflow / Databricks Free Edition | **Databricks Free Edition** | Medallion Bronze/Silver/Gold is the platform's native framing; Unity Catalog gives lineage and governance without building them; AI/BI Dashboards serve the executive view in `kpi-discussion.md` §11 at no extra cost. Free Edition is non-commercial — acceptable for a portfolio project. |
| Table format | Parquet / Iceberg / **Delta Lake** | **Delta Lake** | Default on Databricks; ACID commits make the Gold idempotency requirement (G2) achievable via `MERGE`/`REPLACE` rather than hand-rolled dedupe. Time travel gives a free audit trail for Pillar 7. |
| Compute | Classic clusters / **Serverless** | **Serverless** | The only option on Free Edition. Removes cluster tuning from scope; constrains us to no custom JVM libraries — accepted, none are needed. |
| Transformations | Notebooks only / **dbt-databricks** / Lakeflow Declarative Pipelines | **dbt-databricks** | Transformations become version-controlled SQL with built-in `tests:` — which is how DQ rules stop being prose and become executable. Notebooks are not reviewable as diffs. Declarative Pipelines availability on Free Edition is unconfirmed (§9 OQ-3), so we avoid depending on it. |
| DQ framework | Great Expectations / **dbt tests + custom rules** | **dbt tests + custom** | GE is a heavy second framework for 15 rules; dbt tests already run in the transformation graph and fail the build. Custom Python only for the rules dbt cannot express (geographic plausibility, cross-field duration consistency). |
| Orchestration | Airflow / Dagster / **Databricks Jobs** | **Databricks Jobs (Lakeflow)** | Included in Free Edition; no separate scheduler to host. Revisit if the DAG outgrows it. |
| Geo areas | Official taxi-zone polygons / **coordinate buckets** | **Buckets first** | Contract §8 states the fallback explicitly: no zone lookup is in scope for v1, so `pickup_area` is a normalized geographic bucket. Zone polygons are a documented future enhancement, not a hidden assumption. |
| Auth | PAT / **OAuth service principal (M2M)** | **Service principal where supported, PAT for local dev** | A PAT tied to a human is the confused-deputy risk in Pillar 5. See `SECURITY_CHECKLIST.md`. |

**High-level architecture**

```
Kaggle CSV ──▶ Bronze (Delta, raw+immutable, source_hash tagged)
                  │
                  ├──▶ profile_* tables ──▶ profiling-report.md ──▶ threshold-decisions.md
                  │                                                        │
                  ▼                                     approved thresholds ▼
              Silver (typed, deduped, derived fields, is_valid_trip flags)
                  │                    │
                  │                    └──▶ quarantine (rejected rows + reason)
                  ▼
              Gold: trip_performance · demand_metrics · geographic_metrics
                    vendor_performance · data_quality
                  │
                  ├──▶ AI/BI Dashboard (executive view)
                  └──▶ trusted dataset ──▶ downstream consumers
```

Note the Gold layer has **five** marts, not the six listed in contract §15: `gold_ml_metrics` is
omitted because model performance metrics are out of scope (contract §12).

**Layer contracts**
- **Bronze** — append-only. Never updated, never deleted, never corrected. Carries `source_hash`,
  `ingested_at`, `source_file`. A correction is a new ingestion, not an edit.
- **Silver** — deterministic. Same Bronze rows in, byte-identical Silver rows out. Flags rather
  than deletes (profiling §2: an outlier is not automatically a bad record). Only hard
  business/data-integrity violations are quarantined, and quarantine is a table, not a delete.
- **Gold** — idempotent. A rerun replaces a partition wholesale; it never appends duplicates.

---

## 5. Data model & API contracts

Source schema, DQ rules and KPI definitions are machine-readable — they live in YAML so both the
pipeline and the agent read the same definitions:

- `configs/schema.yml` — the 11 source columns, types, nullability, expected domains
- `configs/quality_rules.yml` — DQ-001..DQ-015, each with severity and reject-vs-flag action
- `configs/kpi_config.yml` — KPI-001..020, each with formula, grain, filter, dimensions

**Derived fields** (Silver, per contract §4): `trip_duration_minutes`, `pickup_date`,
`pickup_year`, `pickup_month`, `pickup_week`, `pickup_day`, `day_of_week`, `pickup_hour`,
`is_weekend`, `time_of_day`, `estimated_distance_km`, `estimated_speed_kmh`, `route_key`,
`is_valid_trip`, `is_duration_outlier`, `is_speed_outlier`.

**Dimensional model** (contract §15):

```
              dim_date
                  │
dim_time ──── fact_trip ──── dim_vendor
                  │
            dim_location
                  │
             dim_route
```

`fact_trip` grain: **one row per valid trip `id`**. Any KPI claiming a different grain must say so
in `configs/kpi_config.yml`.

**Profiling output tables** (profiling spec §29): `profile_run`, `profile_schema`,
`profile_numeric_stats`, `profile_domain_stats`, `profile_quality`, `profile_anomalies`.

---

## 6. Behavior-driven acceptance criteria

These are the definition of "correct" that `EVAL_PLAN.md` verifies.

```
Scenario: BDD-01 — Bronze ingestion is immutable and traceable
  Given a Kaggle source file with a computed SHA256 hash
  When the ingestion job lands it in the Bronze layer
  Then every Bronze row carries that source_hash, source_file and ingested_at
  And re-running the same job with the same file adds no new rows
  And no existing Bronze row is updated or deleted
```

```
Scenario: BDD-02 — A failed data-quality rule is auditable, never silent
  Given a source record that violates a hard rule in configs/quality_rules.yml
  When the Silver transformation runs
  Then the record is written to the quarantine table with its rule id and reason
  And the record is excluded from the valid-trip population
  And total_records equals valid_records plus quarantined_records
```

```
Scenario: BDD-03 — A statistical outlier is flagged, not deleted
  Given a trip whose duration exceeds the approved long-trip threshold
  And whose record violates no hard business rule
  When the Silver transformation runs
  Then the trip is retained with is_duration_outlier set to true
  And the trip still counts toward KPI-001 Total Trips
```

```
Scenario: BDD-04 — Gold aggregation is idempotent
  Given a Gold KPI mart already built for a reporting period
  When the Gold job is re-run for that same period with unchanged Silver input
  Then the KPI values are identical to the previous run
  And no trip is counted twice
```

```
Scenario: BDD-05 — An unapproved threshold cannot reach a KPI
  Given a KPI whose threshold in configs/kpi_config.yml is TBD_PENDING_PROFILING
  When the pipeline attempts to build that KPI
  Then the build fails with an explicit unapproved-threshold error
  And no Gold row is written for that KPI
```

```
Scenario: BDD-06 — Duplicate handling precedes aggregation
  Given a source batch containing duplicate trip ids
  When the pipeline runs
  Then the original duplicate count is preserved in the data-quality audit table
  And KPI-020 Duplicate Rate reports that original count
  And each id contributes at most once to KPI-001 Total Trips
```

```
Scenario: BDD-07 — Estimated distance is never presented as road distance
  Given any surface that displays estimated_distance_km or estimated_speed_kmh
  When the value is rendered in a dashboard, report or column description
  Then it is labelled as estimated or geodesic
  And it is not described as actual route distance or actual road speed
```

---

## 7. Dependencies (pinned)

Verified against PyPI on 2026-08-27 — not recalled from a knowledge cutoff.

| Dependency | Version | Purpose |
|---|---|---|
| python | 3.11 | Runtime; matches Databricks serverless |
| databricks-sdk | 0.133.0 | Workspace, jobs and catalog API |
| databricks-sql-connector | 4.4.0 | Query the SQL warehouse from local tooling |
| dbt-core | 1.12.3 | Transformation graph and tests |
| dbt-databricks | 1.12.4 | dbt adapter for Databricks/Unity Catalog |
| pandas | 3.0.5 | Profiling report assembly (local, small aggregates only) |
| pyyaml | 6.0.3 | Read `configs/*.yml` |
| pytest | 9.1.1 | Deterministic tests in `tests/` |
| ruff | 0.16.4 | Lint + format for Python |
| sqlfluff | 4.3.0 | Lint for SQL models |
| python-dotenv | 1.2.3 | Local env loading; never committed values |

Deferred, not installed: `databricks-connect` (19.1) — only needed if local Spark execution proves
necessary; `great-expectations` (1.21.0) — rejected in §4.

---

## 8. Naming rules the agent must follow

- Bronze `bronze_trips`; Silver `silver_trips`, `silver_trips_quarantine`; Gold `gold_<domain>_*`.
- Any distance or speed field derived from coordinates is prefixed `estimated_` — no exceptions.
- KPI columns carry their id in the model's description so lineage is greppable.
- Durations: store seconds, present minutes; never mix within a single column.

---

## 9. Open questions

| # | Question | Owner | Blocks |
|---|---|---|---|
| OQ-1 | The v1.0 contract defined 24 KPIs; model-performance metrics are now out of scope and the contract covers 20. The **v1.1 record** of that decision is drafted in `kpi-changelog.md` and needs a human approver per contract §20. | Data engineer | Nothing — the config already holds 20 |
| OQ-2 | Six thresholds remain `TBD_PENDING_PROFILING` (long-trip, low-speed, extreme-duration, extreme-distance, geographic outlier, passenger-count anomaly). | Profiling run | KPI-016, KPI-017 |
| OQ-3 | Is Lakeflow Declarative Pipelines available on Free Edition? Architecture avoids depending on it until confirmed. | Data engineer | Nothing — dbt chosen instead |
| OQ-4 | Free Edition serverless quota vs. full-dataset run cost. | Data engineer | Scheduling cadence |
| OQ-5 | `passenger_count = 0` semantics — profiling §9.3 requires investigation before any discard rule. | Profiling run | DQ-008 action |
| OQ-6 | Expected dataset characteristics (row count, date range, vendor domain) are **assumed, not verified**. Profiling confirms them; nothing here hard-codes them. | Profiling run | DQ-003 domain |
