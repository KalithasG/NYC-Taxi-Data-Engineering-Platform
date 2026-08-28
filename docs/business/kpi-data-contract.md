# NYC Taxi Trip Duration — KPI Data Contract

**Document Version:** 1.0  
**Dataset:** NYC Taxi Trip Duration (Kaggle)  
**Purpose:** Define the business KPI contract before designing the data pipeline, data model, transformations and dashboards.  
**Primary Grain:** One taxi trip (`id`) unless otherwise specified.  
**Contract Status:** Draft v1 — thresholds requiring empirical profiling are intentionally not hard-coded.

> **Scope:** 20 KPIs (KPI-001..KPI-020). Model performance metrics are out of scope — see §12.
> The v1.1 record of that scope decision is drafted in `kpi-changelog.md` and awaits human
> approval; `configs/kpi_config.yml` stays at `contract_version: 1.0` until it is signed.

---

## 1. Business Objective

Build a production-style analytics data platform that transforms NYC taxi trip data into trusted business metrics for:

- Trip performance
- Operational efficiency
- Demand analysis
- Geographic analysis
- Vendor performance
- Data quality

The KPI contract is the authoritative definition of what the pipeline must produce.

---

## 2. Source Dataset

### Primary Source

Kaggle — **NYC Taxi Trip Duration**

### Expected Source Columns

| Column | Description | Expected Type |
|---|---|---|
| `id` | Unique trip identifier | String |
| `vendor_id` | Taxi vendor identifier | Integer |
| `pickup_datetime` | Trip pickup timestamp | Timestamp |
| `dropoff_datetime` | Trip drop-off timestamp | Timestamp |
| `passenger_count` | Number of passengers | Integer |
| `pickup_longitude` | Pickup longitude | Decimal |
| `pickup_latitude` | Pickup latitude | Decimal |
| `dropoff_longitude` | Drop-off longitude | Decimal |
| `dropoff_latitude` | Drop-off latitude | Decimal |
| `store_and_fwd_flag` | Whether trip record was stored before forwarding | String |
| `trip_duration` | Trip duration in seconds | Integer |

> `trip_duration` is the primary measure this platform reports on.

---

# 3. KPI Contract Principles

1. Every KPI must have a deterministic definition.
2. KPI calculations must be reproducible from the curated data layer.
3. Raw source data must never be modified.
4. Data-quality filtering must be explicit and auditable.
5. Business thresholds must be derived from profiling where appropriate.
6. All KPIs must specify their calculation grain.
7. KPI definitions must remain stable across pipeline runs.
8. Changes to KPI definitions require a contract version change.
9. Aggregated KPIs must retain enough dimensional information for drill-down.

---

# 4. Common Derived Fields

The Silver layer should derive the following reusable fields.

| Derived Field | Definition |
|---|---|
| `trip_duration_minutes` | `trip_duration / 60` |
| `pickup_date` | Date extracted from `pickup_datetime` |
| `pickup_year` | Year extracted from `pickup_datetime` |
| `pickup_month` | Month extracted from `pickup_datetime` |
| `pickup_week` | Calendar week derived from pickup date |
| `pickup_day` | Day of month |
| `day_of_week` | Day name/number |
| `pickup_hour` | Hour extracted from pickup timestamp |
| `is_weekend` | Saturday/Sunday indicator |
| `time_of_day` | Morning/Afternoon/Evening/Night classification |
| `estimated_distance_km` | Haversine/geodesic distance between pickup and drop-off |
| `estimated_speed_kmh` | Estimated distance divided by trip duration |
| `route_key` | Normalized pickup-zone → drop-off-zone identifier |
| `is_valid_trip` | Record passes mandatory business/data-quality rules |
| `is_duration_outlier` | Duration classified as statistical/business outlier |
| `is_speed_outlier` | Estimated speed classified as anomalous |

### Important Distance Limitation

`estimated_distance_km` is **straight-line/geodesic distance**, not road-network distance.

It must not be described as actual taxi route distance unless road-network data is introduced later.

---

# 5. KPI Summary

| KPI ID | KPI Name | Domain | Grain |
|---|---|---|---|
| KPI-001 | Total Trips | Trip Performance | Dataset/Period |
| KPI-002 | Average Trip Duration | Trip Performance | Dataset/Period + Dimensions |
| KPI-003 | Median Trip Duration | Trip Performance | Dataset/Period + Dimensions |
| KPI-004 | P90 Trip Duration | Trip Performance | Dataset/Period + Dimensions |
| KPI-005 | Average Estimated Distance | Operational Efficiency | Dataset/Period + Dimensions |
| KPI-006 | Average Estimated Speed | Operational Efficiency | Dataset/Period + Dimensions |
| KPI-007 | Trips Per Day | Demand | Date |
| KPI-008 | Trips Per Hour | Demand | Hour |
| KPI-009 | Peak Demand Hour | Demand | Period |
| KPI-010 | Top Pickup Area | Geography | Period |
| KPI-011 | Top Drop-off Area | Geography | Period |
| KPI-012 | Top Route | Geography | Period |
| KPI-013 | Vendor Trip Share | Vendor | Vendor + Period |
| KPI-014 | Vendor Average Duration | Vendor | Vendor + Period |
| KPI-015 | Vendor P90 Duration | Vendor | Vendor + Period |
| KPI-016 | Long Trip Rate | Operations | Period + Dimensions |
| KPI-017 | Low-Speed Trip Rate | Operations | Period + Dimensions |
| KPI-018 | Data Quality Score | Data Quality | Batch/Period |
| KPI-019 | Invalid Record Rate | Data Quality | Batch/Period |
| KPI-020 | Duplicate Rate | Data Quality | Batch/Period |

---

# 6. Detailed KPI Contracts

## KPI-001 — Total Trips

**Domain:** Trip Performance  
**Business Question:** How many valid taxi trips were recorded?

### Definition

Count of unique valid trip IDs.

### Formula

```text
COUNT(DISTINCT id)
```

### Source

- `id`
- `is_valid_trip`

### Filter

```text
is_valid_trip = true
```

### Grain

Dataset / reporting period, optionally segmented by dimensions.

### Dimensions

- Date
- Day of week
- Hour
- Time of day
- Vendor
- Pickup area
- Drop-off area
- Route

### Acceptance Criteria

- `id` must not be null.
- Duplicate IDs must be handled according to the duplicate policy.
- Invalid records must not contribute to the business KPI.

---

## KPI-002 — Average Trip Duration

**Domain:** Trip Performance  
**Business Question:** How long does a taxi trip take on average?

### Formula

```text
AVG(trip_duration)
```

Reported in seconds and minutes.

### Source

- `trip_duration`
- `is_valid_trip`

### Filter

Valid trips only.

### Grain

Period + selected dimensions.

### Acceptance Criteria

- Duration must be positive.
- Extreme/outlier handling must follow the approved data-quality policy.
- Both raw seconds and presentation minutes should be retained.

---

## KPI-003 — Median Trip Duration

**Domain:** Trip Performance  
**Business Question:** What is the typical trip duration without being heavily influenced by extreme trips?

### Formula

```text
PERCENTILE_CONT(0.50, trip_duration)
```

### Source

`trip_duration`

### Filter

Valid trips only.

### Grain

Period + selected dimensions.

### Acceptance Criteria

Median must be calculated from the curated valid-trip population.

---

## KPI-004 — P90 Trip Duration

**Domain:** Trip Performance  
**Business Question:** How long do the slower 10% of trips take?

### Formula

```text
PERCENTILE_CONT(0.90, trip_duration)
```

### Source

`trip_duration`

### Filter

Valid trips only.

### Grain

Period + selected dimensions.

### Business Interpretation

Useful for operational planning because the mean alone can hide long-tail travel times.

---

## KPI-005 — Average Estimated Distance

**Domain:** Operational Efficiency  
**Business Question:** What is the typical geographic distance between pickup and drop-off?

### Formula

```text
AVG(estimated_distance_km)
```

### Derived Field

Haversine/geodesic distance.

### Source

- `pickup_latitude`
- `pickup_longitude`
- `dropoff_latitude`
- `dropoff_longitude`

### Filter

Valid coordinates and valid trips.

### Grain

Period + selected dimensions.

### Acceptance Criteria

- Coordinates must pass geographic plausibility checks.
- Distance must be non-negative.
- Clearly label metric as estimated/geodesic distance.

---

## KPI-006 — Average Estimated Speed

**Domain:** Operational Efficiency  
**Business Question:** How efficiently are trips moving geographically?

### Formula

```text
AVG(estimated_speed_kmh)
```

### Derived Field

```text
estimated_speed_kmh =
estimated_distance_km / trip_duration_hours
```

### Filter

- Valid trips
- Positive duration
- Valid coordinates

### Grain

Period + selected dimensions.

### Warning

This is an estimated speed based on straight-line distance. It is not actual road speed.

---

# 7. Demand KPIs

## KPI-007 — Trips Per Day

**Domain:** Demand  
**Business Question:** How does taxi demand change by date?

### Formula

```text
COUNT(DISTINCT id)
GROUP BY pickup_date
```

### Grain

One row per pickup date.

### Dimensions

Optional vendor, time of day, geography.

### Output

```text
pickup_date
trip_count
```

---

## KPI-008 — Trips Per Hour

**Domain:** Demand  
**Business Question:** Which hours generate the most taxi demand?

### Formula

```text
COUNT(DISTINCT id)
GROUP BY pickup_hour
```

### Grain

Hour of day.

### Recommended Extended Grain

```text
pickup_date + pickup_hour
```

This supports both daily time series and aggregate hourly profiles.

---

## KPI-009 — Peak Demand Hour

**Domain:** Demand  
**Business Question:** What is the busiest hour?

### Definition

Hour with the highest valid trip volume for the selected reporting period.

### Formula

```text
ARGMAX(trip_count BY pickup_hour)
```

### Tie Handling

If multiple hours have equal maximum volume, return all tied hours or apply a deterministic secondary ordering.

### Output

```text
peak_hour
trip_count
reporting_period
```

---

# 8. Geographic KPIs

## KPI-010 — Top Pickup Area

**Domain:** Geography  
**Business Question:** Where do most taxi trips originate?

### Definition

Pickup location/zone with the highest valid trip volume.

### Formula

```text
COUNT(DISTINCT id)
GROUP BY pickup_area
ORDER BY trip_count DESC
LIMIT 1
```

### Initial Implementation

If no official NYC taxi zone lookup is introduced, use normalized geographic buckets.

### Future Enhancement

Join a NYC taxi-zone/geospatial reference dataset.

---

## KPI-011 — Top Drop-off Area

**Domain:** Geography  
**Business Question:** Where do most taxi trips terminate?

### Formula

```text
COUNT(DISTINCT id)
GROUP BY dropoff_area
ORDER BY trip_count DESC
LIMIT 1
```

### Future Enhancement

Use official taxi-zone polygons and spatial joins.

---

## KPI-012 — Top Route

**Domain:** Geography  
**Business Question:** Which pickup → drop-off combination is most frequently travelled?

### Formula

```text
COUNT(DISTINCT id)
GROUP BY pickup_area, dropoff_area
ORDER BY trip_count DESC
LIMIT 1
```

### Route Key

```text
route_key = pickup_area || ' → ' || dropoff_area
```

### Required Companion Metrics

For every high-volume route, also calculate:

- Trip count
- Average duration
- Median duration
- P90 duration
- Average estimated distance
- Average estimated speed

---

# 9. Vendor KPIs

## KPI-013 — Vendor Trip Share

**Domain:** Vendor Performance  
**Business Question:** What proportion of trips is associated with each vendor?

### Formula

```text
vendor_trips / total_trips * 100
```

### Grain

Vendor + reporting period.

### Acceptance Criteria

Vendor shares should sum to approximately 100% for the included vendor population.

---

## KPI-014 — Vendor Average Duration

**Domain:** Vendor Performance  
**Business Question:** How long do trips associated with each vendor take on average?

### Formula

```text
AVG(trip_duration)
GROUP BY vendor_id
```

### Grain

Vendor + period.

---

## KPI-015 — Vendor P90 Duration

**Domain:** Vendor Performance  
**Business Question:** How does slow-trip performance differ between vendors?

### Formula

```text
PERCENTILE_CONT(0.90, trip_duration)
GROUP BY vendor_id
```

### Grain

Vendor + period.

### Interpretation

Lower P90 duration generally indicates better long-tail trip performance, subject to differences in trip mix.

---

# 10. Operational KPIs

## KPI-016 — Long Trip Rate

**Domain:** Operations  
**Business Question:** What proportion of trips are unusually long?

### Formula

```text
long_trips / valid_trips * 100
```

### Threshold

**TBD after data profiling.**

Possible approaches:

1. Business threshold.
2. Percentile-based threshold.
3. IQR-based outlier threshold.
4. Hybrid business + statistical threshold.

### Contract Requirement

The final threshold must be documented and version-controlled.

---

## KPI-017 — Low-Speed Trip Rate

**Domain:** Operations  
**Business Question:** What proportion of trips exhibit unusually low estimated speed?

### Formula

```text
low_speed_trips / valid_trips * 100
```

### Threshold

**TBD after data profiling.**

### Possible Interpretation

Potential indicators include:

- Congestion
- Traffic
- Data anomalies
- Very short geographic movement
- Coordinate quality problems

This KPI must not be interpreted as confirmed congestion without external traffic/road-network data.

---

# 11. Data Quality KPIs

## KPI-018 — Data Quality Score

**Domain:** Data Quality  
**Business Question:** What percentage of source records meet the defined quality rules?

### Formula

```text
valid_records / total_records * 100
```

### Components

At minimum evaluate:

- Null checks
- Duplicate checks
- Timestamp validity
- Duration validity
- Passenger count validity
- Coordinate validity
- Referential/domain validity
- Business-rule validity

### Grain

Batch / ingestion date / source file.

---

## KPI-019 — Invalid Record Rate

**Domain:** Data Quality  
**Business Question:** What proportion of records fail validation?

### Formula

```text
invalid_records / total_records * 100
```

### Relationship

```text
invalid_record_rate = 100 - data_quality_score
```

assuming the quality score is defined strictly as valid/total.

---

## KPI-020 — Duplicate Rate

**Domain:** Data Quality  
**Business Question:** What proportion of source records are duplicates?

### Formula

```text
duplicate_records / total_records * 100
```

### Primary Key

`id`

### Rules

- `id` should be unique.
- Duplicate handling must occur before business aggregation.
- Original duplicate count must be preserved in the data-quality audit table.

---

# 12. Out of Scope — Model Performance Metrics

Metrics that evaluate a predictive model (error metrics such as RMSLE, MAE, RMSE, or percentile
absolute error) are **not part of this contract**.

This platform's job is to produce trusted business measurements from recorded trip data. A model
error metric measures a model, not the taxi operation — it has a different grain (a model run
rather than a trip), a different lifecycle, and a different audience. Mixing the two into one
contract would make "what does this platform measure?" unanswerable.

The contract therefore covers **20 KPIs: KPI-001 through KPI-020.**
# 13. Required Dimensions

The Gold KPI layer should support, where applicable:

| Dimension | Examples |
|---|---|
| Date | 2016-01-01 |
| Month | January |
| Week | Week 1 |
| Day of Week | Monday |
| Hour | 08 |
| Time of Day | Morning |
| Weekend Flag | true/false |
| Vendor | Vendor 1 / Vendor 2 |
| Pickup Area | Geographic zone/bucket |
| Drop-off Area | Geographic zone/bucket |
| Route | Pickup → Drop-off |

---

# 14. Data Quality Rule Contract

The following rules should be implemented before KPI aggregation.

| Rule ID | Validation |
|---|---|
| DQ-001 | `id` must not be null |
| DQ-002 | `id` should be unique |
| DQ-003 | `vendor_id` must be in accepted domain |
| DQ-004 | `pickup_datetime` must not be null |
| DQ-005 | `dropoff_datetime` must not be null |
| DQ-006 | `dropoff_datetime >= pickup_datetime` |
| DQ-007 | `trip_duration > 0` |
| DQ-008 | `passenger_count` must be within defined domain |
| DQ-009 | Pickup coordinates must be geographically plausible |
| DQ-010 | Drop-off coordinates must be geographically plausible |
| DQ-011 | `store_and_fwd_flag` must be within accepted domain |
| DQ-012 | Derived distance must be non-negative |
| DQ-013 | Derived speed must be non-negative |
| DQ-014 | Statistical outliers must be flagged, not silently deleted |
| DQ-015 | All rejected records must be auditable |

---

# 15. KPI Data Model Contract

The eventual Gold layer should support at least these conceptual marts.

```text
gold.trip_performance
gold.demand_metrics
gold.geographic_metrics
gold.vendor_performance
gold.data_quality
```

A possible star-schema direction:

```text
                    dim_date
                       |
                       |
dim_time ---- fact_trip ---- dim_vendor
                       |
                       |
                dim_location
                       |
                       |
                  dim_route
```

The exact physical implementation will be finalized after profiling the source dataset.

---

# 16. KPI Acceptance Criteria

The KPI pipeline is considered valid when:

### Functional

- Every KPI has a deterministic formula.
- KPI outputs can be reproduced from curated data.
- KPI dimensions are consistent.
- KPI calculations exclude records according to documented rules.

### Data Quality

- Invalid records are measurable.
- Duplicate records are measurable.
- Data-quality failures are auditable.
- No silent data loss occurs.

### Engineering

- Raw data remains immutable.
- Silver transformations are deterministic.
- Gold aggregations are idempotent.
- Pipeline reruns do not double-count trips.
- KPI definitions are version-controlled.


---

# 17. KPI Lineage Requirement

Every Gold KPI must have lineage:

```text
Source Column
      ↓
Silver Derived Column
      ↓
Transformation
      ↓
Gold Metric
      ↓
Dashboard / Analytics Consumer
```

Example:

```text
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
        ↓
Haversine Transformation
        ↓
estimated_distance_km
        ↓
AVG(estimated_distance_km)
        ↓
KPI-005 Average Estimated Distance
        ↓
Operations Dashboard
```

---

# 18. Threshold Governance

The following KPI thresholds are intentionally **not fixed in v1**:

- Long-trip threshold
- Low-speed threshold
- Extreme-duration threshold
- Extreme-distance threshold
- Geographic outlier threshold
- Passenger-count anomaly threshold

These must be established after profiling.

### Threshold Decision Process

```text
Raw Data
   ↓
Profiling
   ↓
Distribution Analysis
   ↓
Business Interpretation
   ↓
Candidate Thresholds
   ↓
Validation
   ↓
Approved Threshold
   ↓
KPI Contract v2
```

This prevents arbitrary thresholds from becoming hidden business logic.

---

# 19. Future KPI Extensions

The following are deliberately excluded from v1 because they require additional data or assumptions:

- Actual taxi fare
- Revenue per trip
- Revenue per kilometer
- Driver earnings
- Customer wait time
- Pickup ETA accuracy
- Road-network distance
- Traffic congestion index
- Airport trip performance
- Weather-adjusted trip duration
- Event-adjusted demand
- Service-level agreement compliance

These can be introduced through additional datasets and enrichment pipelines.

---

# 20. KPI Versioning

### Version 1.0

Initial business KPI definitions.

### Version 1.1+

Minor clarifications that do not alter the KPI meaning.

### Version 2.0+

Breaking changes such as:

- Formula changes
- Population/filter changes
- Grain changes
- Threshold changes that materially alter interpretation
- Dimension changes affecting historical comparability

Every KPI change must include:

```text
KPI ID
Old Definition
New Definition
Reason
Effective Date
Impact Assessment
Migration Requirement
```

---

# 21. Final Contract

The following KPIs are approved as the **initial KPI scope** for the NYC Taxi Data Engineering + AI-Driven Development project:

```text
Trip Performance
  KPI-001 Total Trips
  KPI-002 Average Trip Duration
  KPI-003 Median Trip Duration
  KPI-004 P90 Trip Duration

Operational Efficiency
  KPI-005 Average Estimated Distance
  KPI-006 Average Estimated Speed

Demand
  KPI-007 Trips Per Day
  KPI-008 Trips Per Hour
  KPI-009 Peak Demand Hour

Geography
  KPI-010 Top Pickup Area
  KPI-011 Top Drop-off Area
  KPI-012 Top Route

Vendor
  KPI-013 Vendor Trip Share
  KPI-014 Vendor Average Duration
  KPI-015 Vendor P90 Duration

Operations
  KPI-016 Long Trip Rate
  KPI-017 Low-Speed Trip Rate

Data Quality
  KPI-018 Data Quality Score
  KPI-019 Invalid Record Rate
  KPI-020 Duplicate Rate
```

**Next artifact:** Source-data profiling specification → validate actual distributions, identify anomalies, and finalize KPI thresholds before designing the Bronze/Silver/Gold pipeline.
