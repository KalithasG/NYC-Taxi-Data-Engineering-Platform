# Reference — Per-Rule Implementation Notes

Read when implementing a specific rule. Contract: `docs/business/kpi-data-contract.md` §14.
Machine-readable definitions: `configs/quality_rules.yml`.

## Completeness — DQ-001, DQ-004, DQ-005

Straightforward not-null checks on `id`, `pickup_datetime`, `dropoff_datetime`. All **reject**,
all **critical**: without a primary key or a timestamp the row cannot be identified, ordered or
aggregated.

Reasons: `MISSING_PRIMARY_KEY`, `MISSING_PICKUP_TIMESTAMP`, `MISSING_DROPOFF_TIMESTAMP`.

## Uniqueness — DQ-002

The subtle one. Three sub-cases (profiling §26):

| Case | Treatment |
|---|---|
| Exact duplicate row | Deduplicate |
| Same `id`, identical business fields | Deduplicate |
| Same `id`, **conflicting** fields | Quarantine both for review |

Never resolve a conflict by picking the first, the last, or the one with more populated fields.
Two rows claiming to be the same trip with different attributes is an integrity problem, and an
arbitrary tiebreak turns it into an invisible one.

**Order of operations:** count duplicates → write the count to the audit table → deduplicate →
aggregate. KPI-020 reads the audit count. Dedupe first and the metric reports zero.

## Validity — DQ-003, DQ-007, DQ-008, DQ-011

**DQ-003 vendor_id** — domain is `TBD_PENDING_PROFILING`. The observed values are probably `{1, 2}`,
which is exactly what makes hard-coding it tempting; profiling §9.1 says confirm from the source
first. Reject on failure once the domain is approved.

**DQ-007 trip_duration > 0** — reject, critical. A non-positive duration is impossible and would
divide into speed calculations.

**DQ-008 passenger_count** — **flag**, not reject, and deliberately so. Profiling §9.3 says a zero
count needs investigation but must not be discarded before the semantics are understood (spec
OQ-5). Flag column: `is_passenger_count_anomaly`.

**DQ-011 store_and_fwd_flag** — flag. Expected domain `{Y, N}`, but normalise case and whitespace
only *after* profiling records what variants exist. Normalising during ingestion destroys the
evidence of a source-system problem.

## Consistency — DQ-006

`dropoff_datetime >= pickup_datetime`. Reject, critical — logically impossible, the first branch
of the profiling §31 decision tree.

Related but **not** a rule: the duration consistency check (`dropoff - pickup` vs `trip_duration`).
That is a profiling analysis, not a row predicate, because which column is authoritative has not
been decided yet. Do not turn it into a rejection rule without a human decision.

## Geographic — DQ-009, DQ-010

Both reject, both `TBD_PENDING_PROFILING` on the `nyc_bounds` parameter.

Worldwide bounds are necessary but insufficient (profiling §14) — `(0, 0)` is a valid latitude and
longitude and is in the Gulf of Guinea. The bound must reflect the dataset's actual extent.

Classify failures with the GEO taxonomy in `configs/quality_rules.yml`:

```text
GEO-001 null coordinate            GEO-004 outside expected NYC region
GEO-002 impossible latitude        GEO-005 pickup == dropoff      <- do NOT auto-reject
GEO-003 impossible longitude       GEO-006 extremely distant pair
```

GEO-005 is a classification, not a rejection. A zero-distance trip can be real.

## Derived validity — DQ-012, DQ-013

`estimated_distance_km >= 0` and `estimated_speed_kmh >= 0`. Reject, critical — but note what a
failure means: Haversine cannot return a negative distance, so a violation indicates a **defect in
the transformation**, not bad source data. Treat a hit here as a bug report against the pipeline.

## Policies — DQ-014, DQ-015

Not predicates. Enforced by how the pipeline is built, and verified by tests over its behaviour.

**DQ-014** — outliers are flagged, never deleted. Verified by BDD-03: an outlier row survives with
`is_duration_outlier = true` and still counts toward KPI-001. `check_layer_contracts.py` from the
`medallion-transform` skill catches some violations statically.

**DQ-015** — every rejection is auditable. Verified by BDD-02 and the reconciliation
`total == valid + quarantined`.

## Quarantine table shape

```text
silver_trips_quarantine
├── id                    (may be null — DQ-001 rejects land here too)
├── rule_id               DQ-001..DQ-013
├── quarantine_reason     from configs/quality_rules.yml
├── source_hash           which input produced this row
├── quarantined_at
└── <all original source columns, verbatim>
```

Keeping the original columns verbatim is what makes a rejection reversible. If a rule turns out to
be wrong, the rows can be replayed; if only the reason was kept, they cannot.
