# NYC Taxi Data Engineering & Analytics Platform

Converts raw NYC taxi trip data into **trusted business KPIs** through a layered
Bronze/Silver/Gold pipeline with explicit, auditable data-quality rules.

**Platform:** Databricks Free Edition (serverless · Unity Catalog · Delta Lake) ·
**Tier:** structured

| | |
|---|---|
| **Built and verified** | Bronze ingestion · profiling engine · Silver + DQ · 5 Gold marts · 18 of 20 KPIs · 6 dashboard queries · Asset Bundle · CI |
| **Blocked on the dataset** | The profiling *run*, and the 6 thresholds it produces |
| **Blocked on those thresholds** | KPI-016, KPI-017, and 4 partially-enforced DQ rules |

Verified locally against a synthetic fixture: 70 pytest, dbt 28/28, all six contract gates.
Nothing has yet run against the real dataset or a live workspace — see
`docs/architecture/databricks-setup.md`.

---

## Start here

| If you want to… | Read |
|---|---|
| Understand what is being built and why | `specs/nyc-taxi-data-engineering-platform-spec.md` |
| Know what to do next | `PROJECT_PLAN.md` |
| Work in this repo as a coding agent | `AGENTS.md` |
| Look up a KPI's exact formula | `configs/kpi_config.yml` |
| Look up a data-quality rule | `configs/quality_rules.yml` |
| See the business contracts | `docs/business/` |

## The design principle

The pipeline exists to produce **trusted business outcomes**, not to process a dataset. Three
rules follow from that and are enforced rather than merely stated:

1. **No invented thresholds.** Six values sit at `TBD_PENDING_PROFILING`. They are resolved by
   profiling evidence, not by picking a plausible number — and a build that needs one fails.
2. **No silent data loss.** Outliers are flagged, not deleted. Rejections go to a quarantine
   table with a rule id. `total = valid + quarantined` always holds.
3. **No drifting definitions.** Changing a KPI formula requires a contract version bump.

## Run it

```bash
export SPARK_CONF_DIR="$PWD/conf"   # Delta locally, same format as production

# Local — no Databricks account needed. Same Spark SQL engine, so the models are verified
# before they ever reach a workspace.
python tests/fixtures/make_fixture.py --out data/fixture_trips.csv
python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
python -m src.transformations.run --target local --allow-withheld
pytest tests/test_pipeline_e2e.py
```

On Windows use WSL2, or see the PowerShell translation in
`docs/architecture/databricks-setup.md` §1 — Windows PowerShell 5.1 has no `&&`, and Spark needs
Hadoop's Windows binaries before it can write locally.

Databricks Free Edition setup: `docs/architecture/databricks-setup.md`.

## Setup

```bash
# 1. Enable the pre-commit guard (blocks secrets and raw data) — required, once per clone
git config core.hooksPath .githooks

# 2. Credentials — copy and fill in locally. Never commit .env.
cp .env.example .env

# 3. Dataset — see data/README.md. The data is gitignored and the hook blocks committing it.
```

## Layout

```
databricks.yml  Asset Bundle — catalog, schemas, volume, job, grants
resources/      bundle resources (catalog.yml, jobs.yml, permissions.yml)
conf/           local Spark defaults (Delta)
.github/workflows/  CI — contract gates, hook guard, bundle structure, pipeline end-to-end
specs/          source of truth
configs/        machine-readable schema, DQ rules, KPI definitions
docs/           business contracts, profiling, architecture, tools plan
src/            ingestion, profiling, dbt transformations, dashboards, orchestration
tests/          deterministic data tests
evals/          agent trajectory + skill-trigger evals
.agent/skills/  planned reusable skills
.githooks/      pre-commit secret + data guard
```

`tests/` and `evals/` are separate on purpose: tests verify the deterministic parts, evals verify
the non-deterministic ones. See `EVAL_PLAN.md`.

## Scope

**In:** ingestion, profiling, data quality, Bronze/Silver/Gold, data modelling, the 20 business
KPIs, analytics marts, orchestration, dashboard.

**Out:** model training, feature engineering, model registry, prediction serving, and metrics that
evaluate a model rather than the operation (KPI-021..024 in the v1.0 contract — see contract §12).
Also out: fare, revenue, road-network distance and the other extensions listed in the KPI contract
§19, which need datasets this project does not have.

## Source data

Kaggle — *NYC Taxi Trip Duration*. Public, no PII. Not committed to this repository; see
`data/README.md` for acquisition and hashing.
