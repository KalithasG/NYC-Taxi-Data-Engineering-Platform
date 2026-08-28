# Reference — KPI Contract Versioning (§20)

Read when classifying a KPI change or writing a changelog entry.

## The classification test

> Would a chart of this KPI spanning the change be directly comparable across it?

**Yes → 1.1+ (clarification).** The number means the same thing; the description got better.

- Rewording a `note` or `caveat`
- Documenting a dimension that was already computed
- Fixing a typo in a `name` that does not change what is measured
- Adding a `presentation_label` that clarifies an existing caveat

**No → 2.0+ (breaking).** Something about the measurement moved.

- **Formula** — `AVG` → `PERCENTILE_CONT`, adding a `FILTER`, changing units
- **Population/filter** — narrowing or widening which rows count
- **Grain** — per-trip → per-day, or adding a grouping key
- **Threshold** — a change that materially alters interpretation (e.g. long-trip cutoff from P95
  to P99 moves the rate by an order of magnitude)
- **Dimensions** — removing one breaks existing drill-downs

The bar is *historical comparability*, not whether the new definition is better. A change can be a
clear improvement and still be breaking — usually is.

## Borderline cases

**Adding a dimension.** Additive and non-breaking if existing aggregates are unchanged: 1.1.
Breaking if adding it changes an existing rollup — e.g. a dimension that splits previously merged
rows: 2.0.

**Fixing a formula that was wrong.** Still breaking. The old numbers were wrong, which means they
were different, which means they are not comparable. Record it as 2.0 with the bug named in
**Reason** and history handling in **Migration**. A correction with a clear record is fine; a
correction that leaves no trace is the problem.

**Changing a caveat.** Editorial — unless the caveat is what stops the metric being misread. Moving
`estimated_distance_km` from "geodesic distance" to "trip distance" is not editorial; it is a
factual claim change that BDD-07 exists to prevent.

**Renaming a KPI.** The `name` field is semantic here, because it is what appears on dashboards.
1.1 if the meaning is identical and the rename is clarifying; 2.0 if the rename reflects a changed
measurement.

## Writing the two hard fields

**Impact.** Answer three things: who consumes this KPI, whether history stays comparable, and how
much the number moves.

> Weak: "The average will change."
>
> Strong: "Median duration drops ~8% because trips beyond P99 no longer count. The operations
> dashboard and any Q1-Q2 comparison are affected; figures before 2026-09-01 are not comparable
> with figures after. KPI-003 and KPI-004 are unaffected."

**Migration.** State what consumers must do and what happens to history:

- **Rebuild** — recompute Gold for prior periods under the new definition. Comparable series, but
  the archived numbers change, so anything already published moves.
- **Cut over** — new definition from the effective date forward. Archived numbers stay put, but the
  series has a discontinuity that charts must show.
- **Dual-run** — both definitions in parallel for a period. Most work; best when a consumer needs
  time to adapt.

"None" is a legitimate answer when nothing has been published yet — say so explicitly rather than
leaving the field vague.

## Entry template

```markdown
## v2.0 — 2026-09-15

### KPI-016 — Long Trip Rate threshold moved from P95 to P99
- **Old:** long_trips / valid_trips * 100, where long = duration > P95 (5,400s)
- **New:** long_trips / valid_trips * 100, where long = duration > P99 (9,180s)
- **Reason:** P95 flagged 5% of trips by construction, which operations found unactionable.
  Profiling showed a genuine distribution break near P99.
- **Effective:** 2026-09-15
- **Impact:** Long Trip Rate falls from ~5.0% to ~1.0%. Operations dashboard affected;
  pre-2026-09-15 figures are not comparable. No other KPI changes.
- **Migration:** Cut over — history left as computed; the dashboard annotates the change date.
- **Approved by:** <named human>
```

All seven field names are checked by `scripts/check_kpi_contract.py`. It matches on the field
name, so keep the labels even if your wording differs.
