# NYC Taxi Trip Duration — Initial KPI Discussion

**Document Version:** 1.0  
**Dataset:** NYC Taxi Trip Duration — Kaggle  
**Purpose:** Establish the initial business KPI scope for the Data Engineering & Analytics Platform.

---

# 1. Why We Start With KPIs

The project should not begin with tools such as Spark, Airflow, dbt or Kafka.

It should begin with:

```text
Business Questions
        ↓
Business KPIs
        ↓
Data Requirements
        ↓
Data Profiling
        ↓
Data Model
        ↓
Pipeline
        ↓
Analytics
```

This creates a strong Data Engineering design story:

> **The pipeline exists to produce trusted business outcomes, not simply to process a dataset.**

The NYC Taxi Trip Duration dataset is well suited to this because it supports a full operational-analytics story: demand, trip performance, geography, vendor behaviour and data quality.
---

# 2. The Platform — NYC Taxi Data Engineering & Analytics

## Business Objective

Build a production-style data platform that transforms raw taxi-trip data into trusted, queryable business information for operations and analytics teams.

### Core Business Questions

1. How many taxi trips are occurring?
2. When is taxi demand highest?
3. How long do trips normally take?
4. How long do slow trips take?
5. Which pickup and drop-off areas have the highest demand?
6. Which routes are most frequently used?
7. How does trip performance vary by vendor?
8. What percentage of the data is trustworthy?
9. Where are abnormal or suspicious records occurring?

---

# 3. Initial KPI Domains

The platform focuses on six KPI domains:

```text
1. Trip Performance
2. Operational Efficiency
3. Demand
4. Geography
5. Vendor Performance
6. Data Quality
```

Metrics that measure a predictive model rather than the taxi operation are out of scope — see
`kpi-data-contract.md` §12.

---

# 4. Initial Business KPI Set

## Domain 1 — Trip Performance

### KPI-001 — Total Trips

**Question:** How many valid taxi trips are recorded?

```text
COUNT(DISTINCT trip_id)
```

Business value:

- Overall activity
- Volume tracking
- Baseline for other ratios

---

### KPI-002 — Average Trip Duration

**Question:** How long does a taxi trip take on average?

```text
AVG(trip_duration)
```

Business value:

- Overall service-time indicator
- Operational planning

Caution:

Average can be heavily affected by extreme trips.

---

### KPI-003 — Median Trip Duration

**Question:** What is the typical trip duration?

```text
P50(trip_duration)
```

Business value:

More representative than the mean when trip duration is heavily skewed.

---

### KPI-004 — P90 Trip Duration

**Question:** How long do the slower 10% of trips take?

```text
P90(trip_duration)
```

Business value:

Useful for understanding the long tail of travel time.

---

# 5. Domain 2 — Operational Efficiency

## KPI-005 — Average Estimated Distance

**Question:** What is the typical geographic distance between pickup and drop-off?

```text
AVG(estimated_distance_km)
```

Derived from pickup/drop-off coordinates using the Haversine formula.

### Important Limitation

This is:

> **Estimated geodesic distance**

not:

> Actual road distance.

The dashboard and documentation must preserve this distinction.

---

## KPI-006 — Average Estimated Speed

**Question:** What is the average estimated geographic movement speed?

```text
AVG(estimated_speed_kmh)
```

Derived as:

```text
estimated_distance_km
/
trip_duration_hours
```

Business value:

Can help identify unusually slow or fast trips.

It must not be presented as an actual traffic-speed measurement.

---

# 6. Domain 3 — Demand

## KPI-007 — Trips Per Day

```text
COUNT(DISTINCT trip_id)
GROUP BY pickup_date
```

Business value:

- Demand trend
- Daily operational planning
- Anomaly detection

---

## KPI-008 — Trips Per Hour

```text
COUNT(DISTINCT trip_id)
GROUP BY pickup_hour
```

Business value:

Identifies demand patterns throughout the day.

---

## KPI-009 — Peak Demand Hour

```text
ARGMAX(trip_count BY pickup_hour)
```

Business question:

> When is taxi demand at its highest?

This can eventually support:

- Fleet planning
- Driver allocation
- Capacity planning

---

# 7. Domain 4 — Geography

## KPI-010 — Top Pickup Area

Business question:

> Where do most taxi trips originate?

```text
GROUP BY pickup_area
ORDER BY trip_count DESC
```

---

## KPI-011 — Top Drop-off Area

Business question:

> Where do most taxi trips terminate?

```text
GROUP BY dropoff_area
ORDER BY trip_count DESC
```

---

## KPI-012 — Top Route

Business question:

> Which pickup → drop-off route is most frequently travelled?

```text
GROUP BY pickup_area, dropoff_area
ORDER BY trip_count DESC
```

Recommended companion metrics:

```text
trip_count
avg_duration
median_duration
p90_duration
estimated_distance
estimated_speed
```

---

# 8. Domain 5 — Vendor Performance

## KPI-013 — Vendor Trip Share

```text
vendor_trip_count
/
total_trip_count
× 100
```

Business question:

> What proportion of trips is associated with each vendor?

---

## KPI-014 — Vendor Average Duration

```text
AVG(trip_duration)
GROUP BY vendor_id
```

---

## KPI-015 — Vendor P90 Duration

```text
P90(trip_duration)
GROUP BY vendor_id
```

This is preferable to comparing vendors only on averages.

---

# 9. Domain 6 — Operational Anomaly KPIs

## KPI-016 — Long Trip Rate

```text
long_trip_count
/
valid_trip_count
× 100
```

### Threshold

**TBD after actual data profiling.**

Possible methods:

- Percentile
- IQR
- Business-defined threshold
- Hybrid statistical/business threshold

The threshold must not be arbitrarily selected before profiling.

---

## KPI-017 — Low-Speed Trip Rate

```text
low_speed_trip_count
/
valid_trip_count
× 100
```

### Threshold

**TBD after profiling.**

Potential interpretation:

- Congestion candidate
- Geographic anomaly
- Very short trip
- Data issue

It is not proof of traffic congestion.

---

# 10. Domain 7 — Data Quality

Data quality should be treated as a first-class business/engineering product.

## KPI-018 — Data Quality Score

```text
valid_records
/
total_records
× 100
```

---

## KPI-019 — Invalid Record Rate

```text
invalid_records
/
total_records
× 100
```

---

## KPI-020 — Duplicate Rate

```text
duplicate_records
/
total_records
× 100
```

These KPIs demonstrate that the data platform is producing **trusted data**, not simply transformed data.

---

# 11. Executive Dashboard — Initial KPI Set

The first dashboard should avoid showing all 20 KPIs simultaneously.

Recommended executive view:

```text
┌─────────────────────────────────────────────────────────┐
│              NYC TAXI OPERATIONS                        │
├────────────┬────────────┬────────────┬─────────────────┤
│ Total      │ Avg Trip   │ Median     │ P90 Trip        │
│ Trips      │ Duration   │ Duration   │ Duration        │
├────────────┼────────────┼────────────┼─────────────────┤
│ Avg Dist.  │ Avg Speed  │ Peak Hour  │ Data Quality    │
├────────────┴────────────┴────────────┴─────────────────┤
│                                                         │
│             Daily / Hourly Demand Trend                │
│                                                         │
├──────────────────────────┬──────────────────────────────┤
│ Top Pickup Areas         │ Top Routes                  │
│                          │                             │
└──────────────────────────┴──────────────────────────────┘
```

---

# 12. Initial KPI Contract

| ID | KPI | Domain | Priority |
|---|---|---|---|
| KPI-001 | Total Trips | Trip Performance | P0 |
| KPI-002 | Average Trip Duration | Trip Performance | P0 |
| KPI-003 | Median Trip Duration | Trip Performance | P0 |
| KPI-004 | P90 Trip Duration | Trip Performance | P0 |
| KPI-005 | Average Estimated Distance | Efficiency | P1 |
| KPI-006 | Average Estimated Speed | Efficiency | P1 |
| KPI-007 | Trips Per Day | Demand | P0 |
| KPI-008 | Trips Per Hour | Demand | P0 |
| KPI-009 | Peak Demand Hour | Demand | P0 |
| KPI-010 | Top Pickup Area | Geography | P0 |
| KPI-011 | Top Drop-off Area | Geography | P0 |
| KPI-012 | Top Route | Geography | P0 |
| KPI-013 | Vendor Trip Share | Vendor | P1 |
| KPI-014 | Vendor Average Duration | Vendor | P1 |
| KPI-015 | Vendor P90 Duration | Vendor | P1 |
| KPI-016 | Long Trip Rate | Operations | P1 |
| KPI-017 | Low-Speed Trip Rate | Operations | P1 |
| KPI-018 | Data Quality Score | Data Quality | P0 |
| KPI-019 | Invalid Record Rate | Data Quality | P0 |
| KPI-020 | Duplicate Rate | Data Quality | P0 |

---

# 13. Expected Engineering Outcome

The platform should demonstrate:

```text
Data Ingestion
      ↓
Bronze / Raw Layer
      ↓
Schema Validation
      ↓
Data Profiling
      ↓
Data Quality
      ↓
Silver / Clean Layer
      ↓
Business Transformations
      ↓
Gold / KPI Layer
      ↓
Analytics Data Marts
      ↓
Dashboard / BI
```

### Skills Demonstrated

- Data ingestion
- Data profiling
- Data quality engineering
- Data modeling
- SQL
- Distributed processing
- ETL/ELT
- Data transformation
- Dimensional modeling
- Pipeline orchestration
- Testing
- Observability
- Documentation
- CI/CD
- Cloud/data-platform concepts


---

# 14. AI-Driven Development

AI should be treated as an engineering accelerator, not an uncontrolled decision-maker.

AI can assist with:

```text
Requirements
    ↓
KPI Drafting
    ↓
SQL Generation
    ↓
Transformation Code
    ↓
Data Quality Test Generation
    ↓
Documentation
    ↓
Root-Cause Analysis
```

Human review remains required.

---

# 15. Recommended AI Development Guardrails

AI must not independently:

- Change KPI definitions
- Delete production data
- Approve data-quality exceptions
- Introduce target leakage
- Declare a model better without benchmark evidence
- Modify production schemas without review
- Replace automated tests
- Replace reproducible evaluation

The philosophy should be:

```text
AI proposes
     ↓
Automated tests validate
     ↓
Engineer reviews
     ↓
Version control records
     ↓
Pipeline executes
```

---

# 16. Project Boundary

IN SCOPE:

- Source ingestion
- Profiling
- Data quality
- Bronze/Silver/Gold
- Data modeling
- Business KPIs
- Analytics marts
- Orchestration
- Data tests
- Observability
- Dashboard

OUT OF SCOPE:

- Model training
- Hyperparameter optimization
- Model registry
- Prediction serving


---

# 17. Final Initial KPI Decision

Freeze the initial business KPI scope at:

```text
20 Business / Engineering KPIs

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