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

---

# Approved decisions

All six thresholds below were resolved from the completed profiling run
(`profiling_run_id` PROFILE_20260828_180217, source hash
`fc8c777a4ab99a362d8b6b6f2038ff8a2c4625b9593248a47352d0d26fa99927`, 1,458,644 rows). Every
"records affected" figure was measured against `silver.silver_trips` at approval time, not
estimated from the percentile table.

Candidates were proposed by the profiling engine; the values below were chosen and signed by a
human. That split is the point of this document.

## long_trip_seconds

**Value:** `3600` seconds (60 minutes)
**Method:** business, corroborated by percentile
**Evidence:** trip-duration distribution P50 662s · P75 1,075s · P90 1,634s · P95 2,104s ·
P99 3,440s · P99.9 85,128s. Strongly right-skewed. 3,600s sits just beyond P99, so the business
number and the distribution break independently land in the same place.
**Records affected:** 12,317 rows, 0.8444% of the valid population. KPI-016 Long Trip Rate
therefore reports 0.84%.
**Business rationale:** an hour is the point at which a city taxi trip becomes a complaint rather
than a journey. A threshold people can state from memory is one that actually gets used, and this
one is defensible to a stakeholder without showing them a percentile table.
**Alternatives considered:** 3,440s (P99) — purely evidence-derived and flags exactly 1%, but 57
minutes is an awkward figure nobody will repeat correctly. 2,104s (P95) — rejected: flags 5%,
sweeping in ordinary rush-hour trips, which would make "long trip" mean "slightly slow trip".
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** yes — v1.2 → v2.0. KPI-016 moves from withheld to computed (contract §20).
Major rather than minor because the coordinate bounds approved in the same pass shrink the
valid population, so figures either side are not directly comparable.

## low_speed_kmh

**Value:** `5` km/h
**Method:** business
**Evidence:** estimated-speed distribution P25 9.12 km/h · P50 12.79 km/h · P75 17.84 km/h ·
P90 24.35 km/h. Numerator is geodesic, so every figure understates real road speed.
**Records affected:** 71,325 rows, 4.8898% of the valid population. KPI-017 Low-Speed Trip Rate
therefore reports 4.89%.
**Business rationale:** 5 km/h is roughly walking pace. Below it, a metered vehicle is doing
something other than driving — waiting, stuck, or carrying a coordinate problem. It is a floor
that no normally moving trip crosses.
**Alternatives considered:** 9.12 km/h (P25) — rejected outright: flags a quarter of all trips, so
it measures "slower than typical" rather than "anomalous". 3.20 km/h (quarter of median) —
defensible and tighter, but derived from the centre of a geodesic-understated distribution, which
makes it harder to explain than an absolute walking-pace floor.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** yes — v1.2 → v2.0. KPI-017 moves from withheld to computed (contract §20).

**Presentation constraint (BDD-07):** KPI-017 must be labelled a Low-Speed Trip Rate, never a
congestion rate. A low estimated speed has at least six candidate causes and this metric cannot
distinguish between them.

## extreme_duration_seconds

**Value:** `86400` seconds (24 hours)
**Method:** business, corroborated by percentile
**Evidence:** P99.9 = 85,128s (23.6h); observed maximum 3,526,282s (≈41 days). The P99.9 point and
the 24-hour business rule land within half an hour of each other.
**Records affected:** 4 rows, 0.0003% of the valid population — flagged as
`is_duration_outlier`, never removed (DQ-014, BDD-03).
**Business rationale:** a metered taxi trip lasting more than a full day is not a long journey, it
is a meter that was never stopped. Flagging rather than rejecting keeps the rows auditable.
**Alternatives considered:** 85,128s (P99.9) — same practical effect, but not a number anyone can
state or defend from memory. 2,092s (P75 + 1.5×IQR) — rejected: the profiling report explicitly
warns that plain IQR over-flags on a right-skewed distribution and should be read as a lower
bound; it would label roughly 5% of ordinary trips "extreme".
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** no — this drives a flag column, not a KPI formula.

## extreme_distance_km

**Value:** `100` km
**Method:** business
**Evidence:** estimated-distance distribution P99 20.79 km · P99.5 21.56 km · P99.9 24.77 km;
observed maximum 1,240.91 km. Geodesic, so a real route is always longer than the figure shown.
**Records affected:** 19 rows, 0.0013% of the valid population — flagged under GEO-006, not
removed.
**Business rationale:** 100 km is well beyond any plausible metered city trip, so what it catches
is coordinate corruption rather than unusual journeys.
**Alternatives considered:** 24.77 km (P99.9) — rejected: a JFK-to-Manhattan run is roughly 21 km
in a straight line, so a 24.77 km cutoff sits barely above routine airport work and would flag
legitimate trips as extreme. The tail beyond 100 km is a different population entirely.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** no — flag column, not a KPI formula.

## geographic_outlier_bounds

**Value:** latitude `40.4` to `41.0`, longitude `-74.3` to `-73.7` (the same box is written to
`nyc_bounds` in `configs/quality_rules.yml`, which is the name DQ-009 and DQ-010 actually read).
**Method:** business — the documented geographic extent of New York City.
**Evidence:** observed pickup latitude P1 40.644825 – P99 40.806599 with min 34.359695 and max
51.881084; longitude P1 -74.014317 – P99 -73.782227 with min -121.933342 and max -61.335529. The
P1–P99 band is narrow; the min/max show outliers reaching California and the North Atlantic.
**Records affected:** 985 rows, 0.0675% of the valid population, which move to
`silver_trips_quarantine` under DQ-009/DQ-010 with their rule id and reason. They are quarantined,
not deleted, and `total = valid + quarantined` continues to hold.
**Business rationale:** these bounds are a verifiable geographic fact rather than a chosen number,
and they cover all five boroughs plus the airports. Because this rule rejects rather than flags,
erring wide is the safe direction: a false reject removes a real trip from every KPI.
**Alternatives considered:** the observed P1–P99 band (lat 40.6448–40.8066, lon -74.0143–-73.7822)
— rejected: it is purely evidence-derived but describes roughly Manhattan plus a margin, so it
would quarantine genuine Queens, Bronx and Staten Island trips as invalid and reject 2% of the
population by construction.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** yes — this is the change that makes v2.0 major. No KPI *formula* moves, but
the valid population shrinks by 985 rows, so every KPI's denominator changes and figures
either side of this date are not directly comparable.

## passenger_count_anomaly

**Value:** flag when `passenger_count = 0` or `passenger_count > 6`; valid domain `{min: 1, max: 6}`
is written to `passenger_count_domain` for DQ-008 — that is the shape `silver_dq_evaluated.sql`
reads (`.min` / `.max`); a list renders as an empty BETWEEN and fails to compile.
**Method:** business — licensed vehicle capacity.
**Evidence:** observed frequencies — 1: 1,033,540 (70.86%) · 2: 210,318 (14.42%) · 5: 78,088
(5.35%) · 3: 59,896 (4.11%) · 6: 48,333 (3.31%) · 4: 28,404 (1.95%) · 0: 60 (0.0041%) · 7: 3 ·
8: 1 · 9: 1.
**Records affected:** 65 rows, 0.0045% of the valid population — flagged, retained, and visible.
**Business rationale:** six is the maximum for a licensed NYC taxi (a minivan; a sedan is four),
so counts of 7 to 9 cannot be literal. Zero passengers is physically implausible but present.
Profiling spec OQ-5 is explicit that a zero count needs investigation rather than automatic
removal, so this flags and keeps every affected row.
**Alternatives considered:** flag `> 6` only — rejected: leaves the 60 zero-passenger rows
unmarked, which is the exact case OQ-5 raises. Flag `0` only — rejected: treats counts above the
licensed capacity as normal.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** no — DQ flag parameter, no KPI formula change.

## nyc_bounds

The operational twin of `geographic_outlier_bounds` above. Two names exist because
`configs/kpi_config.yml` governs the decision while `configs/quality_rules.yml` holds the value
DQ-009 and DQ-010 actually read — `silver_dq_evaluated.sql` dereferences
`var('nyc_bounds').lat_min` and friends. They must always carry the same box; a divergence would
mean the approved decision and the enforced rule had quietly parted company.

**Value:** `{lat_min: 40.4, lat_max: 41.0, lon_min: -74.3, lon_max: -73.7}`
**Method:** business — the documented geographic extent of New York City.
**Evidence:** observed pickup latitude P1 40.644825 – P99 40.806599 (min 34.359695, max
51.881084); longitude P1 -74.014317 – P99 -73.782227 (min -121.933342, max -61.335529). The
min/max show outliers reaching California and the North Atlantic; the P1–P99 band is far tighter
than the city itself.
**Records affected:** 985 rows measured after the rebuild — 247 rejected by DQ-009 (pickup
outside the box) and 738 by DQ-010 (drop-off outside it), 0.0675% of the population. They move to
`silver_trips_quarantine` with rule id and reason, and `total = valid + quarantined` still holds
at 1,458,644 = 1,457,659 + 985.
**Business rationale:** the box covers all five boroughs plus both airports, and is a verifiable
geographic fact rather than a number someone picked. Because DQ-009/DQ-010 reject rather than
flag, erring wide is the safe direction — a false reject silently removes a real trip from every
KPI.
**Alternatives considered:** the observed P1–P99 band — rejected: purely evidence-derived, but it
describes roughly Manhattan plus a margin and would quarantine genuine Queens, Bronx and Staten
Island trips as invalid, rejecting 2% of the population by construction.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** yes — v1.2 → v2.0. No KPI formula moves, but the valid population shrinks by
985 rows, so every KPI denominator changes and figures either side are not directly comparable.

## passenger_count_domain

The operational twin of `passenger_count_anomaly` above, read by DQ-008 in
`silver_dq_evaluated.sql` as `var('passenger_count_domain').min` / `.max`. The shape matters: a
list renders as an empty `BETWEEN` and fails to compile, which is how the mismatch was caught.

**Value:** `{min: 1, max: 6}` — so `passenger_count = 0` or `> 6` is flagged.
**Method:** business — licensed vehicle capacity.
**Evidence:** observed frequencies 1: 1,033,540 (70.86%) · 2: 210,318 (14.42%) · 5: 78,088
(5.35%) · 3: 59,896 (4.11%) · 6: 48,333 (3.31%) · 4: 28,404 (1.95%) · 0: 60 (0.0041%) · 7: 3 ·
8: 1 · 9: 1.
**Records affected:** 64 rows flagged after the rebuild (0.0044%) — one of the original 65 fell
outside the coordinate bounds and was quarantined instead. All 64 remain in `silver_trips`
carrying `is_passenger_count_anomaly`; DQ-008 flags, it never rejects.
**Business rationale:** six is the maximum for a licensed NYC taxi (a minivan; a sedan is four),
so counts of 7 to 9 cannot be literal. Zero passengers is physically implausible but present in
the source, and profiling spec OQ-5 is explicit that it needs investigation rather than automatic
removal — which is why this flags and retains rather than rejecting.
**Alternatives considered:** flag `> 6` only — rejected: leaves the 60 zero-passenger rows
unmarked, the exact case OQ-5 raises. Flag `0` only — rejected: treats counts above licensed
capacity as normal.
**Approved by:** Kalithas G (kalithas878@gmail.com)
**Effective date:** 2026-08-29
**Contract bump:** no — a flag parameter. No KPI formula changes and no row leaves the population.

## Still pending

**`vendor_domain`** (DQ-003) remains `TBD_PENDING_PROFILING`. Profiling observed exactly two
values — 2: 780,302 (53.50%) and 1: 678,342 (46.51%) — which covers 100% of rows, so `[1,2]` is
the evidenced domain. It was not included in this approval pass and DQ-003 stays unenforced until
it is signed off. DQ-003 rejects, so setting it wrongly quarantines real rows.

## Measured after the rebuild

The "records affected" figures above were measured before the coordinate bounds were enforced.
The rebuild of 2026-08-29 quarantined 985 rows under DQ-009/DQ-010 (247 on pickup, 738 on
drop-off), so the valid population fell from 1,458,644 to 1,457,659 and the rates settled
slightly below their pre-approval estimates:

| Metric | Estimated at approval | Measured after rebuild |
|---|---|---|
| KPI-016 Long Trip Rate | 0.8444% | **0.8348%** |
| KPI-017 Low-Speed Trip Rate | 4.8898% | **4.8788%** |
| Passenger-count anomalies flagged | 65 | **64** (one fell outside the bounds and was quarantined) |
| Duration outliers flagged | 4 | **4** |

The gap is not drift — it is the smaller denominator, and it is exactly why the coordinate-bounds
change was recorded as a major contract version rather than a minor one. Reconciliation holds
after the rebuild: 1,458,644 = 1,457,659 + 985.
