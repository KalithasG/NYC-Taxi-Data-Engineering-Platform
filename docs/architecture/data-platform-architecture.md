# Data Platform Architecture — NYC Taxi Data Engineering Platform

**Version:** 1.0 · **Platform:** Databricks Free Edition · **Spec:** `specs/nyc-taxi-data-engineering-platform-spec.md` §4

---

## 1. Flow

```
Kaggle CSV (data/, gitignored)
        │  SHA256 recorded
        ▼
┌───────────────────────────────────────────────────────────────┐
│ BRONZE — bronze_trips (Delta, append-only)                    │
│ Raw columns verbatim + source_file, source_hash, ingested_at  │
│ CONTRACT: immutable. Never updated, never deleted.            │
└───────────────────────────────────────────────────────────────┘
        │                                    │
        │                                    ▼
        │                     ┌──────────────────────────────┐
        │                     │ PROFILING (one-off + on new  │
        │                     │ source hash)                 │
        │                     │ profile_run, profile_schema, │
        │                     │ profile_numeric_stats,       │
        │                     │ profile_domain_stats,        │
        │                     │ profile_quality,             │
        │                     │ profile_anomalies            │
        │                     └──────────────┬───────────────┘
        │                                    ▼
        │                        profiling-report.md
        │                                    ▼
        │                        threshold-decisions.md
        │                                    │ approved thresholds
        ▼                                    ▼
┌───────────────────────────────────────────────────────────────┐
│ SILVER — silver_trips                                          │
│ Typed · deduplicated · derived fields · DQ flags               │
│ CONTRACT: deterministic. Same Bronze in → identical out.       │
│                                                                │
│   └──▶ silver_trips_quarantine (rejected rows + rule id)      │
└───────────────────────────────────────────────────────────────┘
        ▼
┌───────────────────────────────────────────────────────────────┐
│ GOLD — five marts. CONTRACT: idempotent.                       │
│  gold.trip_performance    KPI-001..006, 016, 017               │
│  gold.demand_metrics      KPI-007..009                         │
│  gold.geographic_metrics  KPI-010..012                         │
│  gold.vendor_performance  KPI-013..015                         │
│  gold.data_quality        KPI-018..020                         │
└───────────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
  AI/BI Dashboard                  Trusted dataset
  (executive view)                 → downstream consumers
```

`gold_ml_metrics` is **absent by design**: metrics that evaluate a model are out of scope for this
platform (KPI contract §12).

## 2. Where each KPI is computed

| Mart | KPIs | Grain |
|---|---|---|
| `gold.trip_performance` | 001, 002, 003, 004, 005, 006, 016, 017 | period + dimensions |
| `gold.demand_metrics` | 007, 008, 009 | date / date+hour / period |
| `gold.geographic_metrics` | 010, 011, 012 | period, by area / route |
| `gold.vendor_performance` | 013, 014, 015 | vendor + period |
| `gold.data_quality` | 018, 019, 020 | batch |

Authoritative definitions live in `configs/kpi_config.yml`. This table is a map, not a second
source of truth — if the two disagree, the YAML wins.

## 3. Dimensional model

```
              dim_date
                  │
dim_time ──── fact_trip ──── dim_vendor
                  │
            dim_location
                  │
             dim_route
```

`fact_trip` grain: one row per valid trip `id`. Dimensions required by KPI contract §13: date,
month, week, day of week, hour, time of day, weekend flag, vendor, pickup area, drop-off area,
route.

## 4. Layer contracts (why each matters)

| Layer | Contract | Failure it prevents |
|---|---|---|
| Bronze | Append-only, hash-tagged | Losing the ability to reproduce any downstream number from the original bytes |
| Silver | Deterministic | Two runs disagreeing, making every KPI unfalsifiable |
| Gold | Idempotent | Reruns double-counting trips (KPI contract §16) |

Practical consequences the agent must respect: no `current_timestamp()` inside a Silver
transformation, no unordered `LIMIT`, no random sampling, and Gold writes replace a partition
rather than appending to it.

## 5. Geographic approach

v1 buckets coordinates into normalized geographic areas. Official NYC taxi-zone polygons and a
spatial join are a **documented future enhancement**, not a hidden assumption — KPI contract §8
names the fallback explicitly. Bucket resolution is set from the coordinate distributions
observed during profiling, not chosen in advance.

## 6. Lineage requirement

Every Gold KPI carries a lineage chain (KPI contract §17):

```
Source Column → Silver Derived Column → Transformation → Gold Metric → Consumer
```

Worked example:

```
pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude
        ↓ Haversine transformation (Earth radius 6371 km)
estimated_distance_km
        ↓ AVG(estimated_distance_km)
KPI-005 Average Estimated Distance
        ↓
Operations dashboard  — labelled "estimated (geodesic)", never "actual route distance"
```

## 7. Unity Catalog layout

Declared in `resources/catalog.yml` and deployed by the Asset Bundle:

```text
${catalog}                     nyc_taxi_dev (dev) · nyc_taxi (prod)
├── bronze      trips_raw, landing volume
├── silver      trips, trips_quarantine
├── gold        the five KPI marts
└── profiling   the six profile_* tables
```

One schema per layer rather than one schema with name prefixes, because the split is what makes
**per-layer grants** expressible. `resources/permissions.yml` gives analysts `SELECT` on `gold`
and nothing else — an analyst who can read Silver can publish a number that never passed the KPI
contract. With everything in one schema that control has nothing to attach to.

> **Applied in contract v1.2** (2026-08-27). The marts moved from `nyc_taxi_dev.gold_<mart>` to
> `gold.<mart>`, and the `mart:` values in `configs/kpi_config.yml` moved with them. `mart` is a
> semantic field under KPI contract §20, so the move carries a signed changelog entry — see
> `kpi-changelog.md`. Bronze, Silver and the profiling tables still share `nyc_taxi_dev`; moving
> them touches no KPI definition, so it is a physical refactor rather than a contract change.
>
> dbt routes Gold via `src/transformations/macros/schema_routing.sql`, which uses a custom schema
> verbatim. dbt's built-in behaviour would prefix it into `nyc_taxi_dev_gold` — a schema neither
> `resources/catalog.yml` creates nor `resources/permissions.yml` grants on.

## 8. Partitioning: none, deliberately

No `PARTITIONED BY`, no Z-ORDER, no liquid clustering — **yet**, and the absence is a decision
rather than an oversight.

Partitioning is a response to a measured problem: known data volume, known query predicates,
known file sizes. None of those are known until the profiling run happens. Partitioning by
year/month now because it is conventional would risk the classic failure — thousands of small
files on a dataset that is a few hundred MB, where the partition pruning saves less than the
metadata overhead costs.

What decides it, once profiling reports actual volume and the dashboard reveals real predicates:

| Signal | Likely response |
|---|---|
| Gold marts stay small (< ~1 GB) | Leave unpartitioned; Delta file skipping is enough |
| Silver grows large, queries filter on `pickup_date` | Liquid clustering on `pickup_date` |
| Consistent high-cardinality filters | Z-ORDER on those columns |
| Genuinely huge and time-sliced | Partition by `pickup_year`, `pickup_month` — no finer |

Record whichever is chosen, and why, in this section.

## 9. Deliberate non-decisions

Recorded so they are not silently settled later by whoever writes the first line of code:

- **Bucket resolution for geographic areas** — set from profiled coordinate distributions.
- **Partitioning strategy for Gold** — chosen once the date range and row counts are known.
- **Whether `passenger_count = 0` is valid** — profiling spec §9.3 requires investigation first.
- **Lakeflow Declarative Pipelines** — not used until Free Edition availability is confirmed
  (spec OQ-3); dbt is the chosen path either way.
