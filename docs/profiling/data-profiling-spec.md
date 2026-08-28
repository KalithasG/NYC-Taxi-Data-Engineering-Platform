# NYC Taxi Trip Duration — Data Profiling Specification & Execution Plan

**Document Version:** 1.0  
**Dataset:** Kaggle NYC Taxi Trip Duration  
**Purpose:** Profile the source dataset before implementing the Bronze/Silver/Gold pipeline and before finalizing KPI thresholds.  
**Status:** Profiling Contract — v1  
**Upstream Contract:** `nyc_taxi_kpi_data_contract.md`

---

# 1. Profiling Objective

The purpose of profiling is to answer:

1. What does the source data actually look like?
2. Are the expected columns present?
3. What are the data types and distributions?
4. How complete and unique is the data?
5. Which records violate business rules?
6. What are the realistic distributions of trip duration, distance and speed?
7. Which anomalies should be **flagged** versus **rejected**?
8. Which KPI thresholds can be safely finalized?
9. What transformations are required for the Silver layer?
10. What data characteristics should influence the Gold data model and ML feature pipeline?

The profiling stage must happen **before** arbitrary outlier thresholds are hard-coded.

---

# 2. Profiling Philosophy

The profiling process follows:

```text
Raw Dataset
     ↓
Schema Profiling
     ↓
Completeness Profiling
     ↓
Uniqueness Profiling
     ↓
Domain Profiling
     ↓
Temporal Profiling
     ↓
Geographic Profiling
     ↓
Trip Duration Profiling
     ↓
Distance / Speed Profiling
     ↓
Anomaly Profiling
     ↓
Data Quality Assessment
     ↓
KPI Threshold Recommendations
     ↓
Profiling Report
```

### Important Principle

An **outlier is not automatically a bad record**.

For example:

- A very long trip may be a legitimate trip.
- A low-speed trip may indicate congestion.
- A geographically distant trip may be legitimate.
- A duplicate may be a genuine duplicate ingestion event.

Therefore the Silver layer should generally **flag first, reject only when the record violates a hard business/data-integrity rule**.

---

# 3. Expected Source Schema

The profiling process must validate the expected schema.

| Column | Expected Type | Required | Profiling |
|---|---|---:|---|
| `id` | String | Yes | Null, unique, duplicate |
| `vendor_id` | Integer | Yes | Domain, frequency |
| `pickup_datetime` | Timestamp | Yes | Null, range, frequency |
| `dropoff_datetime` | Timestamp | Yes | Null, range, ordering |
| `passenger_count` | Integer | Yes | Distribution, invalid values |
| `pickup_longitude` | Decimal | Yes | Range, null, outlier |
| `pickup_latitude` | Decimal | Yes | Range, null, outlier |
| `dropoff_longitude` | Decimal | Yes | Range, null, outlier |
| `dropoff_latitude` | Decimal | Yes | Range, null, outlier |
| `store_and_fwd_flag` | String | Yes | Domain |
| `trip_duration` | Integer | Yes | Distribution, zero, negative, outlier |

---

# 4. Profiling Run Metadata

Every profiling execution should produce a profiling-run record.

| Field | Description |
|---|---|
| `profiling_run_id` | Unique profiling execution ID |
| `source_file` | Source dataset/file |
| `source_hash` | File/content hash |
| `profiling_timestamp` | Execution timestamp |
| `row_count` | Total records |
| `column_count` | Number of columns |
| `pipeline_version` | Code/version used |
| `profile_status` | PASS / WARNING / FAIL |

Example:

```text
profiling_run_id = PROFILE_YYYYMMDD_HHMMSS
source_hash      = SHA256(...)
pipeline_version = git_commit_sha
```

This makes profiling reproducible and auditable.

---

# 5. Phase 1 — File-Level Profiling

## Objectives

Establish basic source characteristics.

### Metrics

- File size
- File format
- Number of files
- Number of rows
- Number of columns
- Header presence
- Encoding
- Compression
- Source checksum/hash

### Acceptance Criteria

- File can be read successfully.
- Expected header is detected.
- No unexplained schema drift exists.
- Row count is recorded.
- Source hash is recorded.

---

# 6. Phase 2 — Schema Profiling

## Checks

For every column:

- Column exists
- Data type
- Nullable
- Distinct count
- Null count
- Null percentage
- Minimum
- Maximum
- Mean where applicable
- Median where applicable
- Standard deviation where applicable

### Schema Drift Rule

If a required source column is missing:

```text
PROFILE_STATUS = FAIL
```

If an unexpected column appears:

```text
PROFILE_STATUS = WARNING
```

unless the pipeline explicitly supports schema evolution.

---

# 7. Phase 3 — Completeness Profiling

Calculate:

```text
null_rate =
null_count / total_records × 100
```

for every column.

### Required Output

| Column | Null Count | Null % | Status |
|---|---:|---:|---|
| `id` | X | X% | PASS/WARN/FAIL |
| `vendor_id` | X | X% | PASS/WARN/FAIL |
| `pickup_datetime` | X | X% | PASS/WARN/FAIL |
| `dropoff_datetime` | X | X% | PASS/WARN/FAIL |
| `passenger_count` | X | X% | PASS/WARN/FAIL |
| coordinates | X | X% | PASS/WARN/FAIL |
| `store_and_fwd_flag` | X | X% | PASS/WARN/FAIL |
| `trip_duration` | X | X% | PASS/WARN/FAIL |

### Initial Policy

Required fields should have:

```text
NULL = 0
```

for valid business records.

Any non-zero rate should be investigated before final acceptance thresholds are set.

---

# 8. Phase 4 — Uniqueness Profiling

## Primary Key

```text
id
```

Calculate:

```text
unique_id_count
duplicate_id_count
duplicate_record_count
duplicate_rate
```

### Formula

```text
duplicate_rate =
duplicate_records / total_records × 100
```

### Required Analysis

Distinguish between:

1. Unique records
2. Repeated IDs
3. Exact duplicate rows
4. Same ID with conflicting attributes

The fourth category is particularly important.

Example:

```text
same id
    ├── identical payload → possible ingestion duplicate
    └── different payload → data integrity issue
```

---

# 9. Phase 5 — Domain Profiling

## 9.1 Vendor

Profile:

```text
COUNT(*)
COUNT(DISTINCT vendor_id)
frequency by vendor_id
```

Validate accepted domain from observed data and business expectations.

Do not hard-code a domain until profiling confirms the source.

---

## 9.2 Store-and-Forward Flag

Profile distinct values.

Expected conceptual domain:

```text
Y
N
```

Check for:

- Lowercase values
- Whitespace
- Null
- Unexpected codes

Normalize only after profiling.

---

## 9.3 Passenger Count

Calculate:

- Minimum
- Maximum
- Mean
- Median
- Frequency distribution
- Zero count
- Negative count
- Extremely high values

Important:

```text
passenger_count = 0
```

requires investigation but should not automatically be discarded without understanding the dataset semantics.

---

# 10. Phase 6 — Temporal Profiling

## Timestamp Integrity

Validate:

```text
pickup_datetime IS NOT NULL
dropoff_datetime IS NOT NULL
dropoff_datetime >= pickup_datetime
```

Calculate:

```text
observed_trip_duration =
dropoff_datetime - pickup_datetime
```

Compare it with:

```text
trip_duration
```

This is one of the most important profiling checks.

---

# 11. Duration Consistency Check

Calculate:

```text
duration_difference =
observed_trip_duration_seconds - trip_duration
```

Profile:

- Minimum difference
- Maximum difference
- Mean difference
- Median difference
- Exact-match percentage
- Non-match percentage

### Objective

Determine whether `trip_duration` is consistent with the pickup/drop-off timestamps.

### Important

Do not assume that every difference represents bad data until the dataset semantics are understood.

---

# 12. Temporal Distribution

Create distributions for:

### Pickup

```text
year
month
week
date
day_of_week
hour
```

### Derived Business Segments

```text
Morning
Afternoon
Evening
Night
```

Recommended initial definition:

```text
Morning   = 05:00–11:59
Afternoon = 12:00–16:59
Evening   = 17:00–20:59
Night     = 21:00–04:59
```

These are **analytical categories**, not business facts, and can be changed after observing demand patterns.

---

# 13. Demand Distribution Profiling

Calculate:

```text
trips_per_day
trips_per_hour
trips_per_weekday
trips_per_month
trips_by_time_of_day
```

Identify:

- Minimum demand date
- Maximum demand date
- Minimum demand hour
- Maximum demand hour
- Weekday/weekend differences
- Seasonal/monthly differences

### Visualization Requirements

Produce:

1. Daily trip-count time series
2. Hour-of-day trip distribution
3. Day-of-week distribution
4. Monthly distribution

---

# 14. Phase 7 — Geographic Profiling

## Coordinate Checks

Profile:

```text
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
```

For each:

- Null count
- Minimum
- Maximum
- Median
- Percentiles
- Distinct count
- Frequency of common coordinates

### Geographic Plausibility

Coordinates must be assessed against the geographic bounds of the source dataset.

Do not blindly use generic worldwide coordinate limits such as:

```text
latitude ∈ [-90, 90]
longitude ∈ [-180, 180]
```

Those checks are necessary but insufficient.

---

# 15. Coordinate Anomaly Categories

Classify coordinate issues into:

```text
GEO-001 Null coordinate
GEO-002 Impossible latitude
GEO-003 Impossible longitude
GEO-004 Outside expected NYC region
GEO-005 Pickup = Drop-off
GEO-006 Extremely distant pickup/drop-off pair
```

Do not automatically reject `pickup = dropoff`.

A zero-distance trip can be real, especially for unusual or very short journeys, but it requires analysis.

---

# 16. Haversine Distance Profiling

Derive:

```text
estimated_distance_km
```

using the Haversine formula.

### Formula

```text
a =
sin²((lat₂-lat₁)/2)
+
cos(lat₁) × cos(lat₂) × sin²((lon₂-lon₁)/2)

c = 2 × atan2(√a, √(1-a))

distance = Earth_radius × c
```

Use:

```text
Earth radius ≈ 6371 km
```

### Profile

- Minimum distance
- Maximum distance
- Mean
- Median
- P50
- P75
- P90
- P95
- P99
- Zero-distance rate
- Extreme-distance rate

---

# 17. Phase 8 — Trip Duration Profiling

This is the most important analytical profiling stage because `trip_duration` is both:

1. A core business KPI input.
2. The ML target.

Calculate:

```text
MIN
MAX
MEAN
MEDIAN
STDDEV
P25
P50
P75
P90
P95
P99
```

Report both:

```text
seconds
minutes
```

---

# 18. Duration Distribution Analysis

Generate:

1. Histogram
2. Box plot
3. Percentile table
4. Log-scale distribution
5. Duration by hour
6. Duration by weekday
7. Duration by vendor

### Why Log Distribution?

Trip duration is expected to be highly right-skewed.

The log-scale view helps reveal:

- Long-tail behavior
- Extreme observations
- Distribution shape
- Potential data-entry anomalies

---

# 19. Duration Outlier Detection

Use multiple methods rather than one rule.

## Method A — Percentiles

Calculate:

```text
P90
P95
P99
P99.5
P99.9
```

## Method B — IQR

```text
IQR = P75 - P25

Upper Bound = P75 + 1.5 × IQR
```

## Method C — Log-space analysis

Calculate:

```text
log1p(trip_duration)
```

and examine its distribution.

### Decision

Do not automatically delete all statistical outliers.

Instead classify:

```text
NORMAL
LONG_BUT_PLAUSIBLE
EXTREME_REVIEW
INVALID
```

---

# 20. Duration Hard-Validation Rules

Candidate hard rules:

```text
trip_duration IS NOT NULL
trip_duration > 0
```

Additional maximum-duration limits must be determined after profiling.

### Required Output

```text
zero_duration_count
negative_duration_count
extreme_duration_count
```

---

# 21. Phase 9 — Speed Profiling

Calculate:

```text
estimated_speed_kmh =
estimated_distance_km /
(trip_duration / 3600)
```

Profile:

- Minimum
- Maximum
- Mean
- Median
- P90
- P95
- P99
- Zero-distance trips
- Very-low-speed trips
- Very-high-speed trips

---

# 22. Speed Anomaly Analysis

Speed is useful because it combines:

```text
distance
+
duration
```

Potential categories:

```text
SPEED-001 Zero-distance trip
SPEED-002 Very-low estimated speed
SPEED-003 Very-high estimated speed
SPEED-004 Geographic anomaly
SPEED-005 Duration anomaly
```

### Important Interpretation Rule

A low estimated speed is **not proof of traffic congestion**.

Possible causes include:

- Traffic
- Long route versus straight-line distance
- Pickup/drop-off coordinates
- Waiting time included in duration
- GPS/data issues
- Legitimate unusual trip

---

# 23. Cross-Field Profiling

The following relationships must be analyzed.

### A. Duration vs Distance

```text
estimated_distance_km
        vs
trip_duration
```

Expected relationship:

```text
longer distance → generally longer duration
```

Investigate major deviations.

---

### B. Duration vs Hour

Identify whether travel time changes during:

- Morning
- Afternoon
- Evening
- Night

---

### C. Duration vs Day of Week

Compare:

```text
Monday ... Sunday
```

---

### D. Duration vs Vendor

Compare vendor distributions without assuming one vendor is operationally superior because trip mixes may differ.

---

### E. Distance vs Speed

Investigate:

```text
short distance + extremely long duration
long distance + extremely short duration
```

These combinations are useful anomaly candidates.

---

# 24. Phase 10 — Vendor Profiling

For each vendor calculate:

```text
trip_count
trip_share
avg_duration
median_duration
p90_duration
avg_distance
median_distance
avg_speed
long_trip_rate
```

### Distribution Analysis

Do not compare vendors using only averages.

Compare:

```text
P50
P90
P95
```

because trip-duration distributions are likely skewed.

---

# 25. Phase 11 — Store-and-Forward Profiling

Calculate:

```text
trip_count by store_and_fwd_flag
percentage by flag
avg_duration by flag
median_duration by flag
P90 duration by flag
```

This provides an additional operational dimension.

Do not infer causality from this comparison.

---

# 26. Phase 12 — Duplicate Profiling

Classify duplicates into:

### Type A

Exact duplicate rows.

### Type B

Duplicate `id` with identical business fields.

### Type C

Duplicate `id` with conflicting fields.

### Required Metrics

```text
exact_duplicate_rate
duplicate_id_rate
conflicting_duplicate_rate
```

### Recommended Handling

| Duplicate Type | Initial Treatment |
|---|---|
| Exact duplicate | Deduplicate |
| Same ID, same payload | Deduplicate |
| Same ID, conflicting payload | Quarantine/review |
| Unique ID | Accept subject to validation |

---

# 27. Data Quality Score Model

The initial KPI contract defines:

```text
Data Quality Score =
valid_records / total_records × 100
```

For profiling, additionally calculate component scores:

```text
Completeness Score
Uniqueness Score
Validity Score
Consistency Score
Geographic Validity Score
```

These component metrics should be reported separately before deciding whether to combine them into a weighted quality score.

---

# 28. Recommended Data Quality Dimensions

```text
                    DATA QUALITY
                         |
       ┌─────────────────┼─────────────────┐
       ↓                 ↓                 ↓
 Completeness        Validity          Uniqueness
       │                 │                 │
     Nulls          Domain rules       Duplicate IDs
                       │
                       ↓
                  Consistency
                       │
                Timestamp vs Duration
                       │
                       ↓
                  Geographic
                       │
               Coordinate plausibility
```

---

# 29. Profiling Output Tables

The profiling pipeline should generate these datasets/tables.

## `profile_run`

```text
profiling_run_id
source_file
source_hash
profiling_timestamp
pipeline_version
row_count
column_count
profile_status
```

## `profile_schema`

```text
profiling_run_id
column_name
data_type
nullable
distinct_count
null_count
null_rate
```

## `profile_numeric_stats`

```text
profiling_run_id
column_name
min
max
mean
stddev
p25
p50
p75
p90
p95
p99
```

## `profile_domain_stats`

```text
profiling_run_id
column_name
value
count
percentage
```

## `profile_quality`

```text
profiling_run_id
rule_id
rule_name
total_records
failed_records
failure_rate
status
```

## `profile_anomalies`

```text
profiling_run_id
anomaly_type
record_count
percentage
severity
recommended_action
```

---

# 30. Profiling Report

The final profiling report should contain:

## Executive Summary

```text
Dataset size
Date range
Schema status
Overall data quality
Major anomalies
Major distribution characteristics
Recommended actions
```

## Data Quality Summary

```text
Null rate
Duplicate rate
Invalid coordinate rate
Invalid duration rate
Timestamp inconsistency rate
```

## Business Distribution Summary

```text
Trip volume
Duration distribution
Distance distribution
Speed distribution
Peak demand
Vendor distribution
```

## Anomaly Summary

```text
Anomaly type
Count
Percentage
Severity
Treatment
```

## KPI Threshold Recommendations

For every KPI with a TBD threshold:

```text
KPI
Candidate threshold
Evidence
Expected impact
Recommended action
```

---

# 31. Threshold Decision Framework

Use the following decision tree:

```text
Observed Anomaly
       ↓
Is it logically impossible?
       │
   ┌───┴───┐
  YES      NO
   ↓        ↓
Reject   Is it statistically extreme?
              │
          ┌───┴───┐
         YES      NO
          ↓        ↓
       Flag     Normal
          ↓
Is there business evidence it is valid?
          │
      ┌───┴───┐
     YES      NO
      ↓        ↓
   Retain   Review/Flag
```

This avoids over-cleaning the dataset.

---

# 32. Profiling-to-KPI Decisions

After profiling, finalize these KPI contract items:

| KPI | Profiling Decision Required |
|---|---|
| KPI-002 Average Duration | Valid population |
| KPI-004 P90 Duration | Valid population |
| KPI-005 Distance | Coordinate validity |
| KPI-006 Speed | Duration/distance treatment |
| KPI-016 Long Trip Rate | Long-duration threshold |
| KPI-017 Low-Speed Rate | Low-speed threshold |
| KPI-018 Data Quality Score | Hard validation population |
| KPI-019 Invalid Rate | Hard validation rules |
| KPI-020 Duplicate Rate | Duplicate treatment |

---

# 33. Profiling Success Criteria

The profiling phase is complete only when:

- [ ] Source schema is validated.
- [ ] All columns have completeness statistics.
- [ ] Primary-key uniqueness is measured.
- [ ] Duplicate categories are identified.
- [ ] Timestamp ranges are understood.
- [ ] Pickup/drop-off temporal distributions are understood.
- [ ] Coordinate distributions are understood.
- [ ] Geographic anomalies are quantified.
- [ ] Trip-duration distribution is understood.
- [ ] Distance distribution is understood.
- [ ] Speed distribution is understood.
- [ ] Vendor distributions are compared.
- [ ] Store-and-forward distributions are profiled.
- [ ] Cross-field inconsistencies are measured.
- [ ] Hard-invalid records are identified.
- [ ] Statistical outliers are identified but not blindly deleted.
- [ ] KPI thresholds requiring empirical evidence are proposed.
- [ ] Profiling results are reproducible.
- [ ] Profiling artifacts are version-controlled.

---

# 34. Recommended Profiling Execution Order

```text
STEP 01
Download / acquire source dataset
        ↓
STEP 02
Calculate source hash
        ↓
STEP 03
Validate schema
        ↓
STEP 04
Profile completeness
        ↓
STEP 05
Profile uniqueness
        ↓
STEP 06
Profile domains
        ↓
STEP 07
Profile timestamps
        ↓
STEP 08
Validate duration consistency
        ↓
STEP 09
Profile geographic coordinates
        ↓
STEP 10
Calculate Haversine distance
        ↓
STEP 11
Calculate estimated speed
        ↓
STEP 12
Profile distributions
        ↓
STEP 13
Detect anomalies
        ↓
STEP 14
Generate data-quality report
        ↓
STEP 15
Recommend KPI thresholds
        ↓
STEP 16
Update KPI Contract → v1.1/v2.0 if required
```

---

# 35. AI-Driven Development Integration

The profiling stage should be one of the first places where AI assists engineering without becoming the source of truth.

### AI can assist with

```text
Raw Profiling Results
        ↓
AI Analysis
        ↓
Anomaly Explanation
        ↓
Candidate Data Quality Rules
        ↓
Candidate KPI Thresholds
        ↓
Engineer Review
        ↓
Approved Rules
```

### AI must NOT independently

- Delete records.
- Change KPI definitions.
- Approve thresholds.
- Modify production schemas.
- Mark anomalies as invalid without deterministic rules.

The deterministic profiling engine remains authoritative.

---

# 36. Suggested Project Artifact Structure

```text
nyc-taxi-data-platform/
│
├── docs/
│   ├── business/
│   │   └── kpi-data-contract.md
│   │
│   ├── profiling/
│   │   ├── data-profiling-spec.md
│   │   ├── profiling-report.md
│   │   └── threshold-decisions.md
│   │
│   └── architecture/
│       └── data-platform-architecture.md
│
├── data/
│   └── README.md
│
├── src/
│   ├── ingestion/
│   ├── profiling/
│   ├── transformations/
│   ├── quality/
│   └── features/
│
├── tests/
│   ├── data_quality/
│   ├── transformations/
│   └── kpi/
│
├── configs/
│   ├── schema.yml
│   ├── quality_rules.yml
│   └── kpi_config.yml
│
└── README.md
```

---

# 37. Final Profiling Deliverable

The profiling phase should ultimately produce four key artifacts:

```text
1. profiling-report.md
   ↓
   What the data actually looks like

2. data-quality-report
   ↓
   What is wrong / suspicious

3. threshold-decisions.md
   ↓
   What business thresholds should be used

4. updated-kpi-contract
   ↓
   Final measurable business definitions
```

Only after these are available should the project proceed to:

```text
Data Profiling
      ↓
KPI Contract Finalization
      ↓
Data Architecture
      ↓
Data Model
      ↓
Bronze Layer
      ↓
Silver Layer
      ↓
Gold Layer
      ↓
Data Quality Framework
      ↓
Orchestration
      ↓
Feature Engineering
      ↓
ML Training
      ↓
ML Benchmarking
      ↓
ML Monitoring
      ↓
AI-Driven Development Layer
```

---

# 38. Immediate Next Action

The next practical step is to run this profiling specification against the actual Kaggle training dataset and produce an **evidence-based profiling report**.

The profiling report must replace all `TBD` thresholds with recommendations backed by:

- Actual distributions
- Percentiles
- Invalid-record counts
- Outlier analysis
- Cross-field consistency
- Business interpretation

**Do not finalize KPI thresholds before this profiling run.**
