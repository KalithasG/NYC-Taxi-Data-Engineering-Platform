# Data Profiling Report — NYC Taxi Trip Duration

**Generated:** 2026-08-28T18:03:18.889798+00:00  
**Produced by:** `src/profiling/run_profiling.py`, executing `docs/profiling/data-profiling-spec.md` §34.

> This report classifies; it does not clean. No row was dropped, corrected or excluded. An outlier is not automatically a bad record (spec §2) — the counts below are evidence for a human decision, not a decision.

---

## Profiling run metadata

| Field | Value |
|---|---|
| `profiling_run_id` | PROFILE_20260828_180217 |
| `source_file` | train.csv |
| `source_hash` | fc8c777a4ab99a362d8b6b6f2038ff8a2c4625b9593248a47352d0d26fa99927 |
| `profiling_timestamp` | 2026-08-28T18:02:18.776592+00:00 |
| `row_count` | 1,458,644 |
| `column_count` | 14 |
| batches (distinct source_hash) | 1 |
| `profile_status` | PASS |

The source hash is what makes this run reproducible and ties every number below to an exact input file.

## Output tables (spec §29)

This report is the version-controlled artifact; these tables are the working detail and hold the full per-column and per-value breakdowns behind the summaries below.

| Table | Contents |
|---|---|
| `profile_run` | One row per profiling execution: run id, source file and hash, timestamps, row and column counts, status |
| `profile_schema` | Per-column null counts and null rates |
| `profile_numeric_stats` | Min/max/mean/stddev and P25–P99.9 for duration, distance and speed |
| `profile_domain_stats` | Value frequencies for vendor_id, store_and_fwd_flag and passenger_count |
| `profile_quality` | Per-rule DQ evaluation: failed records, failure rate, status |
| `profile_anomalies` | Anomaly class counts (GEO-*, zero/negative duration, zero distance) with severity |

Regenerate with `python -m src.profiling.run_profiling --write-tables`.

## Executive summary

- **Dataset size:** 1,458,644 rows, 14 columns
- **Date range:** 2016-01-01 to 2016-06-30 (182 distinct dates)
- **Schema status:** all expected source columns present (validated against `configs/schema.yml`)
- **Uniqueness:** 1,458,644 distinct ids; 0 rows carry a duplicated id (0.0000%)
- **Duration consistency:** 100.00% of rows have `trip_duration` exactly equal to the pickup/drop-off interval
- **Major anomalies:** 0 null-coordinate, 5,897 zero-distance (pickup = drop-off), 0 zero-duration, 0 negative-duration
- **Recommended action:** review the threshold candidates at the end of this report, then approve values via the `threshold-decision` skill.

## Completeness

Null rate per column. Required fields should be 0; any non-zero rate is investigated before an acceptance threshold is set (spec §7).

| Column | Null count | Null % | Status |
|---|---:|---:|---|
| `id` | 0 | 0.0000% | PASS |
| `vendor_id` | 0 | 0.0000% | PASS |
| `pickup_datetime` | 0 | 0.0000% | PASS |
| `dropoff_datetime` | 0 | 0.0000% | PASS |
| `passenger_count` | 0 | 0.0000% | PASS |
| `pickup_longitude` | 0 | 0.0000% | PASS |
| `pickup_latitude` | 0 | 0.0000% | PASS |
| `dropoff_longitude` | 0 | 0.0000% | PASS |
| `dropoff_latitude` | 0 | 0.0000% | PASS |
| `store_and_fwd_flag` | 0 | 0.0000% | PASS |
| `trip_duration` | 0 | 0.0000% | PASS |

## Uniqueness and duplicates

- Distinct ids: **1,458,644**
- Ids appearing more than once: **0**
- Rows carrying a duplicated id: **0** (0.0000%)
- Exact duplicate rows (all columns identical): **0**

Duplicate categories (spec §26). The third is the one that matters: same id with conflicting fields is a data-integrity problem, and resolving it by picking either row turns a visible problem into an invisible one.

| Type | Meaning | Treatment |
|---|---|---|
| A | Exact duplicate row | Deduplicate |
| B | Same id, identical payload | Deduplicate |
| C | Same id, conflicting payload | Quarantine for review |

KPI-020 must read this pre-deduplication count (0), not the deduplicated table.

## Domain profiling

### `vendor_id`

| Value | Count | % |
|---|---:|---:|
| 2 | 780,302 | 53.4950% |
| 1 | 678,342 | 46.5050% |

### `store_and_fwd_flag`

| Value | Count | % |
|---|---:|---:|
| N | 1,450,599 | 99.4485% |
| Y | 8,045 | 0.5515% |

### `passenger_count`

| Value | Count | % |
|---|---:|---:|
| 1 | 1,033,540 | 70.8562% |
| 2 | 210,318 | 14.4187% |
| 5 | 78,088 | 5.3535% |
| 3 | 59,896 | 4.1063% |
| 6 | 48,333 | 3.3136% |
| 4 | 28,404 | 1.9473% |
| 0 | 60 | 0.0041% |
| 7 | 3 | 0.0002% |
| 8 | 1 | 0.0001% |
| 9 | 1 | 0.0001% |

`vendor_id` and `passenger_count` domains stay `TBD_PENDING_PROFILING` in `configs/quality_rules.yml` until a human confirms them from the evidence above (spec §9.1, §9.3). `passenger_count = 0` requires investigation, not automatic removal — that is spec OQ-5.

## Temporal profiling and duration consistency

Pickup range **2016-01-01 → 2016-06-30** across 182 dates.

### Duration consistency check (spec §11)

Comparing `dropoff_datetime - pickup_datetime` against the `trip_duration` column. This is the single most important comparison in the run: every duration-based KPI rests on these two agreeing.

| Metric | Value |
|---|---|
| Exact matches | 1,458,644 (100.0000%) |
| Mismatches | 0 (0.0000%) |
| Min difference | 0 s |
| Max difference | 0 s |
| Mean difference | 0 s |
| Median difference | 0 s |

No verdict is offered on which column is authoritative. Spec §11 is explicit that a difference is not assumed to be bad data until the dataset semantics are understood.

### Distribution by hour of day

| Hour | Trips |
|---:|---:|
| 0 | 53,248 |
| 1 | 38,571 |
| 2 | 27,972 |
| 3 | 20,895 |
| 4 | 15,792 |
| 5 | 15,002 |
| 6 | 33,248 |
| 7 | 55,600 |
| 8 | 67,053 |
| 9 | 67,663 |
| 10 | 65,437 |
| 11 | 68,476 |
| 12 | 71,873 |
| 13 | 71,473 |
| 14 | 74,292 |
| 15 | 71,811 |
| 16 | 64,313 |
| 17 | 76,483 |
| 18 | 90,600 |
| 19 | 90,308 |
| 20 | 84,072 |
| 21 | 84,185 |
| 22 | 80,492 |
| 23 | 69,785 |

### Distribution by day of week

| Day | Trips |
|---|---:|
| Friday | 223,533 |
| Saturday | 220,868 |
| Thursday | 218,574 |
| Wednesday | 210,136 |
| Tuesday | 202,749 |
| Sunday | 195,366 |
| Monday | 187,418 |

## Geographic profiling

Coordinate ranges. Worldwide bounds are necessary but insufficient (spec §14) — `(0, 0)` is a valid latitude and longitude and sits in the Gulf of Guinea.

| Measure | Min | P1 | P99 | Max |
|---|---|---|---|---|
| pickup_latitude | 34.359695 | 40.644825 | 40.806599 | 51.881084 |
| pickup_longitude | -121.933342 | -74.014317 | -73.782227 | -61.335529 |

### Coordinate anomalies (spec §15)

| Code | Meaning | Count | % |
|---|---|---:|---:|
| GEO-001 | Null coordinate | 0 | 0.0000% |
| GEO-002 | Impossible latitude | 0 | 0.0000% |
| GEO-003 | Impossible longitude | 0 | 0.0000% |
| GEO-004 | At (0,0) — outside any plausible NYC region | 0 | 0.0000% |
| GEO-005 | Pickup = drop-off | 5,897 | 0.4043% |

GEO-005 is a classification, not a rejection. A zero-distance trip can be real — a cancelled journey, a round trip, a very short hop.

## Trip duration distribution

| Statistic | min | mean | stddev | max | p25 | p50 | p75 | p90 | p95 | p99 | p995 | p999 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| value | 1 | 959.4923 | 5,237.4317 | 3,526,282 | 397 | 662 | 1,075 | 1,634 | 2,104 | 3,440 | 4,139 | 85,128.357 |

Units: seconds.

| In minutes | P50 | P90 | P95 | P99 | P99.9 |
|---|---|---|---|---|---|
| value | 11 | 27.2 | 35.1 | 57.3 | 1,418.8 |

Hard-rule violations: **0** zero-duration, **0** negative, **0** null.

**IQR bound (spec §19 Method B):** IQR = 678, upper = P75 + 1.5×IQR = 2,092 s.

Trip duration is expected to be strongly right-skewed, so a symmetric-distribution method over-flags. Read the IQR bound as a lower bound on the candidate range rather than an answer.

Outlier classification (spec §19): rows are graded `NORMAL` / `LONG_BUT_PLAUSIBLE` / `EXTREME_REVIEW` / `INVALID`. Only `trip_duration IS NOT NULL` and `trip_duration > 0` are hard rules; a maximum comes from the decision recorded in `threshold-decisions.md`. Statistical outliers are identified here and **not deleted** (DQ-014).

## Estimated distance distribution

Geodesic Haversine distance (Earth radius 6371 km). **Not road distance** — real routes are longer by a factor that varies with the route, so the error is not a constant that can be corrected for.

| Statistic | min | mean | stddev | max | p25 | p50 | p75 | p90 | p95 | p99 | p995 | p999 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| value | 0 | 3.4409 | 4.2965 | 1,240.9087 | 1.2318 | 2.0937 | 3.8753 | 7.6308 | 11.0193 | 20.7875 | 21.5574 | 24.7668 |

Units: kilometres.

Zero-distance trips: **5,897** (0.4043%).

## Estimated speed distribution

Derived as `estimated_distance_km / (trip_duration / 3600)`. Because the numerator is geodesic, this systematically understates real driving speed.

| Statistic | min | mean | stddev | max | p25 | p50 | p75 | p90 | p95 | p99 | p995 | p999 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| value | 0 | 14.4232 | 14.9783 | 9,276.9573 | 9.1213 | 12.792 | 17.8449 | 24.3539 | 29.4417 | 40.7453 | 44.8577 | 54.302 |

Units: km/h.

A low estimated speed is **not** proof of congestion (spec §22). Candidate causes: traffic, a real route much longer than the straight line, waiting time inside the duration, coordinate quality, or a genuinely unusual trip.

## Vendor profiling

Compared on P50/P90/P95, not averages alone: the distributions are skewed and trip mixes differ, so an average gap may say nothing about performance (spec §24).

| Vendor | Trips | Avg duration | P50 | P90 | P95 | Avg est. distance | Avg est. speed |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 678,342 | 845.4 | 658 | 1,613 | 2,063 | 3.4035 | 14.3894 |
| 2 | 780,302 | 1,058.6 | 666 | 1,652 | 2,142 | 3.4733 | 14.4526 |

## Store-and-forward profiling

| Flag | Trips | % | Avg duration | P50 | P90 |
|---|---:|---:|---:|---:|---:|
| N | 1,450,599 | 99.4485% | 958.8 | 662 | 1,630 |
| Y | 8,045 | 0.5515% | 1,080.8 | 812 | 2,251.2 |

No causality is inferred from this comparison (spec §25).

## Data quality summary

Per-rule evaluation. `BLOCKED_PENDING_THRESHOLD` means the rule's parameter is still unset, so only the decidable part could be evaluated — recorded rather than silently passed.

| Rule | Name | Failed | Failure rate | Status |
|---|---|---:|---:|---|
| DQ-001 | `id_not_null` | 0 | 0.0000% | PASS |
| DQ-002 | `id_unique` | 0 | 0.0000% | PASS |
| DQ-003 | `vendor_id_in_domain` | — | — | BLOCKED_PENDING_THRESHOLD |
| DQ-004 | `pickup_datetime_not_null` | 0 | 0.0000% | PASS |
| DQ-005 | `dropoff_datetime_not_null` | 0 | 0.0000% | PASS |
| DQ-006 | `dropoff_not_before_pickup` | 0 | 0.0000% | PASS |
| DQ-007 | `trip_duration_positive` | 0 | 0.0000% | PASS |
| DQ-008 | `passenger_count_in_domain` | — | — | BLOCKED_PENDING_THRESHOLD |
| DQ-009 | `pickup_coordinates_plausible` | — | — | BLOCKED_PENDING_THRESHOLD |
| DQ-010 | `dropoff_coordinates_plausible` | — | — | BLOCKED_PENDING_THRESHOLD |
| DQ-011 | `store_and_fwd_flag_in_domain` | 0 | 0.0000% | PASS |
| DQ-012 | `estimated_distance_non_negative` | 0 | 0.0000% | PASS |
| DQ-013 | `estimated_speed_non_negative` | 0 | 0.0000% | PASS |
| DQ-014 | `outliers_flagged_never_deleted` | — | — | POLICY |
| DQ-015 | `rejections_are_auditable` | — | — | POLICY |

### Component scores (spec §27)

Reported separately before any weighted blend — one combined number hides which dimension is failing, which is the thing you need to know.

| Dimension | Score |
|---|---:|
| Completeness (required fields) | 100.0000% |
| Uniqueness | 100.0000% |
| Consistency (timestamp ordering) | 100.0000% |
| Geographic validity | 100.0000% |

## KPI threshold recommendations

**Candidates only. Nothing here is approved, and this engine does not write to `configs/kpi_config.yml`.** Each threshold needs a human decision recorded in `docs/profiling/threshold-decisions.md` with an approver's name (contract §18, spec §31).

### `long_trip_seconds` — blocks KPI-016 Long Trip Rate

| # | Candidate | Method | Flags | Argument |
|---|---|---|---:|---|
| A | 2,104 s (35 min) | percentile P95 | 5.0% | Fixed, predictable review volume; flags many ordinary rush-hour trips. |
| B | 3,440 s (57 min) | percentile P99 | 1.0% | Flags only the genuinely unusual tail. |
| C | 3,600 s (60 min) | business | — | A round hour is legible to stakeholders and easy to state from memory. |

A threshold people can state from memory gets used. Where the business number and a distribution break agree, that agreement is itself evidence worth recording.

### `low_speed_kmh` — blocks KPI-017 Low-Speed Trip Rate

| # | Candidate | Method | Flags | Argument |
|---|---|---|---:|---|
| A | 9.12 km/h | percentile P25 | 25% | Too broad for an anomaly flag. |
| B | 3.20 km/h | quarter of median | — | Relative to the observed centre rather than an absolute guess. |
| C | 5 km/h | business | — | Roughly walking pace; below it, something is unusual. |

**A low estimated speed is not proof of congestion.** The numerator is geodesic, so this metric systematically understates road speed. Whatever value is chosen, KPI-017 must be presented as an anomaly-candidate rate, not a congestion rate (BDD-07).

### `extreme_duration_seconds` — blocks `is_duration_outlier` flag

| # | Candidate | Method | Flags | Argument |
|---|---|---|---:|---|
| A | 85,128 s (23.6 h) | percentile P99.9 | 0.1% | Very tail-only. |
| B | 2,092 s | IQR (P75 + 1.5×IQR) | — | Over-flags on a right-skewed distribution; treat as a lower bound. |
| C | 86,400 s (24 h) | business | — | A trip longer than a day is implausible. |

This flags rows; it never removes them (DQ-014, BDD-03).

### `extreme_distance_km` — blocks GEO-006

| # | Candidate | Method | Flags | Argument |
|---|---|---|---:|---|
| A | 24.77 km | percentile P99.9 | 0.1% | Distribution tail. |
| B | 100 km | business | — | Beyond plausible range for a metered city trip. |

Geodesic distance, so a legitimate long trip appears shorter than it drove.

### `nyc_bounds` — blocks DQ-009 / DQ-010

Observed pickup coordinate range:

- latitude  P1 40.644825 … P99 40.806599 (min 34.359695, max 51.881084)
- longitude P1 -74.014317 … P99 -73.782227 (min -121.933342, max -61.335529)

The P1–P99 band is a defensible starting point; the min/max gap shows how far the outliers reach. Note that a tighter bound rejects more rows, and rejection is not reversible in the KPI — it is reversible only because the quarantine table keeps the original columns.

## Profiling success criteria (spec §33)

- [x] Source schema is validated.
- [x] All columns have completeness statistics.
- [x] Primary-key uniqueness is measured.
- [x] Duplicate categories are identified.
- [x] Timestamp ranges are understood.
- [x] Pickup/drop-off temporal distributions are understood.
- [x] Coordinate distributions are understood.
- [x] Geographic anomalies are quantified.
- [x] Trip-duration distribution is understood.
- [x] Distance distribution is understood.
- [x] Speed distribution is understood.
- [x] Vendor distributions are compared.
- [x] Store-and-forward distributions are profiled.
- [x] Cross-field inconsistencies are measured (duration consistency).
- [x] Hard-invalid records are identified.
- [x] Statistical outliers are identified but not blindly deleted.
- [x] KPI thresholds requiring empirical evidence are proposed.
- [x] Profiling results are reproducible (source_hash recorded).
- [x] Profiling artifacts are version-controlled (this report is committed; git tracks it).

