---
name: data-profiling-runner
description: "Runs and validates the source-data profiling for the NYC taxi dataset — the 16-step order in docs/profiling/data-profiling-spec.md §34 that produces the six profile_* tables and docs/profiling/profiling-report.md. Use this whenever asked to profile the data, explore or inspect the dataset, check data quality before building, find out what the data actually looks like, investigate nulls, duplicates, coordinate ranges, duration or speed distributions, or answer 'is this data any good'. Also use when a threshold or a KPI is blocked pending profiling evidence, when someone asks whether profiling is finished, and before writing any Silver transformation — profiling comes first, and this is the step every threshold and DQ rule is waiting on."
---

# Data Profiling Runner

This is the step everything else is waiting on. Six thresholds, three DQ domains, KPI-016, KPI-017
and the entire Silver layer are blocked until a profiling run produces evidence. It is also the
last moment where the dataset can be understood before assumptions get baked into code.

The governing principle, from profiling spec §2:

> An outlier is not automatically a bad record.

A very long trip, a very slow trip, a zero-distance trip and a duplicate can all be legitimate.
Profiling *quantifies* them so a human can decide; it does not clean them.

## Is profiling actually done?

```bash
python3 .claude/skills/data-profiling-runner/scripts/check_profiling_complete.py
```

Checks the report against profiling spec §33 (19 success criteria), §29 (six output tables) and §4
(run metadata), and rejects a report that still carries `_pending_` placeholders or lacks a real
SHA256 source hash.

Treat it as a floor, not a proof. It confirms each topic was addressed; it cannot confirm the
analysis was any good. A report that passes this and says nothing useful is still a bad report.

## Before you start

You need the dataset, and it is not in the repo — `data/README.md` has acquisition steps. **Record
the SHA256 first.** Without it the run is unreproducible and every downstream number is untraceable
to an input, which is what `profiling_run_id` and `source_hash` exist to prevent.

## The 16 steps (spec §34)

Full detail in `references/profiling-phases.md`. The order matters — later steps depend on
derivations made in earlier ones.

| Steps | Phase | Produces |
|---|---|---|
| 01-02 | Acquire, hash | `profile_run` |
| 03 | Validate schema | `profile_schema` — missing required column = FAIL, unexpected column = WARNING |
| 04-05 | Completeness, uniqueness | null rates; duplicate types A/B/C |
| 06 | Domains | `profile_domain_stats` — vendor, store_and_fwd, passenger_count |
| 07-08 | Timestamps, **duration consistency** | the most important check — see below |
| 09-11 | Coordinates, Haversine distance, speed | `profile_numeric_stats` |
| 12-13 | Distributions, anomalies | `profile_anomalies` |
| 14 | Data-quality report | `profile_quality` |
| 15 | Recommend thresholds | the hand-off to `threshold-decision` |
| 16 | Update the KPI contract if required | the hand-off to `kpi-contract-guard` |

## The check that matters most

Step 08. Compute `dropoff_datetime - pickup_datetime` and compare it against the `trip_duration`
column:

```text
duration_difference = observed_trip_duration_seconds - trip_duration
```

Report min, max, mean, median, exact-match percentage and non-match percentage. If these disagree,
every duration-based KPI in this platform rests on an unexplained inconsistency.

Resist the urge to declare a winner. Profiling spec §11 is explicit: do not assume a difference is
bad data until the dataset semantics are understood. Quantify the disagreement, characterise its
shape, and let a human decide which column is authoritative.

## What to write down

`docs/profiling/profiling-report.md` already has the required section headings. Fill them, and for
every anomaly class give **count, percentage, severity and recommended treatment** — not just a
narrative. Classify coordinates as GEO-001..006 and speed as SPEED-001..005
(`configs/quality_rules.yml` carries both taxonomies), and grade duration outliers
NORMAL / LONG_BUT_PLAUSIBLE / EXTREME_REVIEW / INVALID.

Then stop. Recommending thresholds is step 15 and belongs to **`threshold-decision`**; changing a
KPI belongs to **`kpi-contract-guard`**. Profiling produces evidence, not decisions.

## Two habits worth keeping

**Report seconds and minutes.** Duration percentiles in raw seconds are hard to reason about; a
reviewer who has to convert P99 in their head will skim it instead.

**Look at duration in log space.** Trip duration is expected to be strongly right-skewed, so the
linear histogram will be a spike at the left with an invisible tail. `log1p(trip_duration)` is
where the distribution's actual shape — and any data-entry artefacts — become visible.
