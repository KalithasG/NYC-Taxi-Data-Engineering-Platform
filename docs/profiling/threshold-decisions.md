# Threshold Decisions — NYC Taxi Data Engineering Platform

**Status:** BLOCKED — awaiting `profiling-report.md`.
**Governs:** the six `TBD_PENDING_PROFILING` values in `configs/kpi_config.yml`.

> A threshold recorded here without evidence is invisible business logic. This file exists so that
> every cutoff has a traceable justification and an approver.

## Open thresholds

| # | Threshold | Config key | Blocks | Status |
|---|---|---|---|---|
| T1 | Long-trip duration | `thresholds.long_trip_seconds` | KPI-016 | open |
| T2 | Low-speed cutoff | `thresholds.low_speed_kmh` | KPI-017 | open |
| T3 | Extreme duration | `thresholds.extreme_duration_seconds` | `is_duration_outlier` | open |
| T4 | Extreme distance | `thresholds.extreme_distance_km` | GEO-006 | open |
| T5 | Geographic bounds | `thresholds.geographic_outlier_bounds` | DQ-009, DQ-010 | open |
| T6 | Passenger-count anomaly | `thresholds.passenger_count_anomaly` | DQ-008 | open |

Also open: the `vendor_id` accepted domain (DQ-003) and the `passenger_count` domain (DQ-008),
both marked `TBD_PENDING_PROFILING` in `configs/quality_rules.yml`.

## Decision framework (profiling spec §31)

```
Observed anomaly
      ↓
Is it logically impossible? ──YES──▶ Reject
      │NO
      ▼
Is it statistically extreme? ──NO──▶ Normal
      │YES
      ▼
Flag ──▶ Is there business evidence it is valid? ──YES──▶ Retain
                                                 └─NO───▶ Review / Flag
```

This ordering is what stops the dataset being over-cleaned. An outlier is not automatically a bad
record: a very long trip, a low-speed trip, and a zero-distance trip can all be legitimate.

## Required record per decision

Each resolved threshold must document:

```
Threshold ID
Candidate value
Method            (business | percentile | IQR | hybrid)
Evidence          (percentiles, affected record count, distribution shape)
Records affected  (count and % of valid population)
Business rationale
Alternative values considered and why rejected
Approved by       (a human — never the agent)
Effective date
KPI contract version bump required?
```

## Contract impact

Resolving T1 and T2 changes how KPI-016 and KPI-017 are computed, which under KPI contract §20 is
a **material change**. Expect a contract version bump; record it with KPI ID, old definition, new
definition, reason, effective date, impact assessment and migration requirement.

The pending **v1.1 record** of the model-metric scope exclusion (spec OQ-1) should be signed off in
the same pass.
