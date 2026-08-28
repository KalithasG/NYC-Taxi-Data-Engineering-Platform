# Data

**Nothing in this directory is committed.** `.gitignore` excludes it and `.githooks/pre-commit`
blocks it — the dataset is Kaggle-licensed and large. Both guards are deliberate; do not work
around either.

## Acquire

Source: Kaggle — **NYC Taxi Trip Duration**.

```bash
# Kaggle CLI (needs ~/.kaggle/kaggle.json — never commit it)
kaggle competitions download -c nyc-taxi-trip-duration -p data/
unzip data/nyc-taxi-trip-duration.zip -d data/
```

Or download `train.csv` manually from the competition's Data tab into `data/`.

## Record the hash before anything else

Every Bronze row carries the source hash, which is what makes re-ingestion idempotent (BDD-01)
and profiling reproducible.

```bash
sha256sum data/train.csv
```

Record the value in `docs/profiling/profiling-report.md` under `source_hash`.

## Expected schema

11 columns, defined in `configs/schema.yml`: `id`, `vendor_id`, `pickup_datetime`,
`dropoff_datetime`, `passenger_count`, `pickup_longitude`, `pickup_latitude`, `dropoff_longitude`,
`dropoff_latitude`, `store_and_fwd_flag`, `trip_duration`.

Row count, date range and vendor domain are **deliberately not stated here.** They are assumptions
until the profiling run confirms them (spec OQ-6).

## Licence

Kaggle competition data, subject to the competition rules. Redistribution via this repository is
not permitted — which is the other reason the hook blocks it.
