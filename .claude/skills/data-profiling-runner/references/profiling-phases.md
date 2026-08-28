# Reference — Profiling Phases in Detail

Read when executing a phase. Source: `docs/profiling/data-profiling-spec.md`.

## Run metadata (§4) — do this first

```text
profiling_run_id  = PROFILE_YYYYMMDD_HHMMSS
source_file       = data/train.csv
source_hash       = SHA256(...)          <- without this the run is unreproducible
profiling_timestamp
row_count / column_count
pipeline_version  = git commit sha
profile_status    = PASS | WARNING | FAIL
```

## Phase 2 — Schema (§6)

Per column: exists, data type, nullable, distinct count, null count, null %, min, max, mean,
median, stddev where applicable.

**Drift rule.** Required column missing → `profile_status = FAIL`. Unexpected column present →
`WARNING`, unless schema evolution is explicitly supported. Expected columns are in
`configs/schema.yml`.

## Phase 3 — Completeness (§7)

`null_rate = null_count / total_records × 100` for every column. Required fields should be 0. Any
non-zero rate is investigated *before* an acceptance threshold is set, not after.

## Phase 4 — Uniqueness (§8)

Four categories, and the fourth is the one that matters:

```text
same id
    ├── identical payload  -> probable ingestion duplicate
    └── different payload  -> data integrity issue
```

Report `unique_id_count`, `duplicate_id_count`, `duplicate_record_count`, `duplicate_rate`. The
original pre-deduplication count must survive into the audit table — KPI-020 reads it, and
deduplicating before counting would make the metric report zero forever.

## Phase 5 — Domains (§9)

- **vendor_id** — frequency by value. Do not hard-code the accepted domain until profiling
  confirms the source (this is DQ-003's pending parameter).
- **store_and_fwd_flag** — distinct values, plus lowercase variants, whitespace, nulls and
  unexpected codes. Normalise only *after* profiling; normalising first hides what was there.
- **passenger_count** — min/max/mean/median, frequency, zero count, negative count, extreme highs.
  `passenger_count = 0` needs investigation, not automatic deletion (this is spec OQ-5).

## Phase 6 — Temporal (§10-13)

Validate not-null and `dropoff >= pickup`. Then the duration consistency check (§11) — the single
most important comparison in the whole run.

Distributions for year, month, week, date, day_of_week, hour, and the time-of-day buckets. Those
buckets (Morning 05:00-11:59, Afternoon 12:00-16:59, Evening 17:00-20:59, Night 21:00-04:59) are
**analytical categories, not business facts** — they can change once demand patterns are visible.

Four visualisations are required: daily time series, hour-of-day, day-of-week, monthly.

## Phase 7 — Geographic (§14-16)

Per coordinate column: null count, min, max, median, percentiles, distinct count, frequency of
common values.

Generic worldwide bounds (`lat ∈ [-90,90]`, `lon ∈ [-180,180]`) are **necessary but insufficient** —
a coordinate in the Atlantic passes them. Assess against the dataset's actual geographic extent.

Haversine, Earth radius 6371 km. Profile min, max, mean, median, P50/P75/P90/P95/P99, zero-distance
rate, extreme-distance rate.

Do not auto-reject `pickup == dropoff` (GEO-005). A zero-distance trip can be real — a cancelled
journey, a round trip, a very short hop — and rejecting it silently discards a signal.

## Phase 8-9 — Duration and speed (§17-22)

Duration: MIN, MAX, MEAN, MEDIAN, STDDEV, P25, P50, P75, P90, P95, P99 — in seconds *and* minutes.
Then histogram, box plot, percentile table, log-scale distribution, and duration by hour, weekday
and vendor.

Outlier detection uses three methods, not one: percentiles (P90/95/99/99.5/99.9), IQR
(`P75 + 1.5×IQR`), and log-space analysis. Classify rather than delete:

```text
NORMAL | LONG_BUT_PLAUSIBLE | EXTREME_REVIEW | INVALID
```

Only `trip_duration IS NOT NULL` and `trip_duration > 0` are hard rules. A maximum comes later,
from evidence.

Speed: `estimated_distance_km / (trip_duration / 3600)`. A low value is **not** proof of
congestion — candidates include traffic, route-vs-straight-line divergence, waiting time inside the
duration, coordinate quality, and genuinely unusual trips.

## Phase 10-12 — Vendor, store-and-forward, duplicates (§24-26)

Compare vendors on P50/P90/P95, never on averages alone — the distributions are skewed and trip
mixes differ, so an average difference may say nothing about performance.

Duplicate handling: exact duplicate → deduplicate; same id + same payload → deduplicate; same id +
conflicting payload → **quarantine for review**, never silently pick one.

## Cross-field checks (§23)

Duration vs distance · duration vs hour · duration vs day of week · duration vs vendor ·
distance vs speed. The last is the richest anomaly source: short distance with extremely long
duration, and long distance with extremely short duration.

## Output tables (§29)

`profile_run` · `profile_schema` · `profile_numeric_stats` · `profile_domain_stats` ·
`profile_quality` · `profile_anomalies` — column lists are in the spec.

## Component quality scores (§27)

Report completeness, uniqueness, validity, consistency and geographic validity **separately**
before deciding whether to combine them into a weighted score. A single blended number hides which
dimension is failing, which is the one thing you need to know.
