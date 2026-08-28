# src/profiling/

Executes `docs/profiling/data-profiling-spec.md` §34 — the sixteen steps that produce the six
`profile_*` tables and `docs/profiling/profiling-report.md`.

```bash
python -m src.profiling.run_profiling --local --write-tables            # local
python -m src.profiling.run_profiling --catalog nyc_taxi --write-tables # Databricks
```

Requires `bronze_trips` and the `silver_typed` view, so run ingestion and at least
`dbt run --select silver_typed` first.

## Two rules it follows without exception

**It classifies; it never cleans.** No row is dropped, corrected or excluded. An outlier is not
automatically a bad record (spec §2) — a very long trip, a very slow trip and a zero-distance
trip can all be real. The counts are evidence for a human decision, not the decision.

**It proposes thresholds; it never sets one.** The recommendations section carries percentiles,
affected-record counts and two or three candidates each. `configs/kpi_config.yml` is not
touched. Approving a value is a human act recorded in `threshold-decisions.md` — see the
`threshold-decision` skill.

## Where it reads from, and why

| Phase | Source | Reason |
|---|---|---|
| Schema, completeness, uniqueness, domains | `bronze_trips` | These checks are about the raw landing data |
| Distributions, geography, duration, speed | `silver_typed` | Typing and derivations, no filtering and no thresholds — reusing it avoids a second copy of the Haversine formula, and a duplicated derivation eventually disagrees with itself |

`silver_typed` is safe to depend on here precisely because it applies no threshold. Profiling
produces the thresholds, so depending on anything that consumed one would be circular.

## Verifying it

`docs/profiling/example-report-from-fixture.md` is a real run against the synthetic fixture —
proof the engine works, and a preview of the output format. Reproduce it with:

```bash
python tests/fixtures/make_fixture.py --out data/fixture_trips.csv
python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
python -m src.transformations.run --target local --allow-withheld
python -m src.profiling.run_profiling --local --write-tables
```

`check_profiling_complete.py` then accepts the result — and still rejects the stub, so passing
it means the run actually happened rather than the headings being right.
