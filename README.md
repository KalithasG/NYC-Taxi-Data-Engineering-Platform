# NYC Taxi Data Engineering & Analytics Platform

**A medallion lakehouse that turns 1.46 million raw taxi trips into trusted business KPIs — where
"trusted" is enforced by code, not asserted in a README.**

Built on Databricks (serverless · Unity Catalog · Delta Lake) with dbt, deployed as a Databricks
Asset Bundle, and developed end-to-end with AI agents working under executable guardrails.

```
Kaggle CSV (191 MB)  →  BRONZE  →  SILVER + DQ  →  GOLD marts  →  AI/BI dashboard
  1,458,644 rows        append-     1,457,659 valid  20 KPIs       21 panels
                        only,       985 quarantined  5 marts
                        hashed      + flags
                            └──────► PROFILING ──► 6 tables + evidence report
```

---

## The problem this is built around

Most data pipelines fail quietly. A KPI definition drifts. An outlier cutoff gets picked because
it looked reasonable. A few thousand awkward rows are dropped so a metric behaves. Nothing in the
codebase notices — the dashboard stays green, the tests stay passing, and the business acts on a
number nobody can trace.

This platform is designed so those three failures **cannot happen silently**:

| Rule | Enforcement |
|---|---|
| **No invented thresholds** | Six cutoffs shipped as `TBD_PENDING_PROFILING`. A build needing one **fails** (BDD-05) — it does not substitute a default. Releasing one requires distribution evidence, alternatives weighed, and a named human approver. |
| **No silent data loss** | Outliers are *flagged*, never deleted. Rejected rows go to a quarantine table with the rule id that rejected them. `total = valid + quarantined` is asserted as a dbt test on every build. |
| **No drifting definitions** | Changing a KPI's formula, filter, grain or dimensions requires a contract version bump plus a seven-field changelog entry. A pre-commit gate blocks the commit otherwise. |

The payoff: every number on the dashboard traces to a source column, a transformation, and a
recorded decision with someone's name on it.

---

## Verified on real data

Not a fixture. The pipeline runs on Databricks against the real Kaggle dataset — 1,458,644 rows,
January–June 2016 — and the following were confirmed by querying the live tables, not by reading
the code:

| Check | Result |
|---|---|
| Full 4-task job | `TERMINATED / SUCCESS` on serverless |
| dbt build | `PASS=28  WARN=0  ERROR=0` — 9 models + 19 data tests |
| Reconciliation | `1,458,644 total = 1,457,659 valid + 985 quarantined` — exact, with the rule id on every rejected row |
| All 20 KPIs building | thresholds approved 2026-08-29; gate run **hard** (`allow_withheld=false`) and passed |
| KPI-016 / KPI-017 | 0.8348% and 4.8788%, computed from approved thresholds rather than withheld |
| Bronze idempotency (BDD-01) | 4 repeated ingests → still 1,458,644 rows, one `source_hash`, zero duplication |
| Bronze append-only | `DESCRIBE HISTORY` contains no mutating operation |
| Gold not double-counting (BDD-04) | KPI-001 sums to exactly the valid population, 1,457,659 |
| Threshold gate (BDD-05) | Blocked by default and refused to build until the thresholds carried evidence and a named approver |
| Contract gates | 5/5 pass · the profiling report satisfies its own completeness checker |

Before the geographic bounds were approved, quarantine was empty — and that was **checked against
raw Bronze rather than trusted**, because a rule that never fires produces exactly the same number
as a rule with nothing to catch. The raw data genuinely had 0 null ids, 0 duplicate ids, 0
inverted timestamps and a minimum duration of 1 s, so the reject rules had nothing to reject.

With the coordinate bounds now approved, 985 rows are quarantined — 247 on pickup (DQ-009), 738 on
drop-off (DQ-010) — each carrying its rule id and reason, and none deleted. The distinction between
reject and flag holds throughout: the 64 out-of-range passenger counts and the 4 trips over 24
hours are *flagged and retained* in `silver_trips`, because a suspicious trip is still a trip that
happened.

---

## Architecture

```
              configs/*.yml ─────────────┐   11-column schema · 15 DQ rules · 20 KPI definitions
              (the contract)             │   read at build time, never restated in SQL
                                         ▼
 /Volumes/…/train.csv ──► BRONZE ──► SILVER ─────────────────► GOLD ──► dashboard
                          append-    silver_typed   (view)     trip_performance
                          only,      silver_dq_evaluated (view) demand_metrics
                          hashed,    silver_trips              geographic_metrics
                          immutable  silver_trips_quarantine   vendor_performance
                                          │                    data_quality
                                          └── flags vs rejects ─── reconciliation test
                          PROFILING ──► profile_run · profile_schema · profile_numeric_stats
                                        profile_domain_stats · profile_quality · profile_anomalies
```

| Layer | Contract it must satisfy |
|---|---|
| **Bronze** | Append-only and immutable. Every row carries `source_file`, `source_hash`, `ingested_at`. A correction is a new ingestion, never an edit. No `MERGE` — idempotency comes from the hash check, because MERGE updates rows in place, which is exactly what the contract forbids. |
| **Silver** | Deterministic. Same Bronze in, byte-identical Silver out. No `current_timestamp()`, no random sampling, no non-deterministic ordering. Flags first; quarantine only on a hard rule. |
| **Gold** | Idempotent. A rerun replaces a partition wholesale and never appends duplicates. |

One Unity Catalog schema per layer — not cosmetic. It is what makes per-layer grants expressible:
an analyst who can read Silver can publish a number that bypassed the KPI contract, so analysts
get `SELECT` on `gold` and nothing else.

---

## AI-driven development

This platform was built by AI agents. The engineering that makes that *trustworthy* is the part
worth reading — an agent that can quietly redefine a KPI or invent a threshold is worse than no
agent at all.

**An instruction layer, not vibes.** `AGENTS.md` is the cross-tool contract every agent reads:
five inviolable rules, the layer contracts, naming conventions, and an explicit list of forbidden
actions. `CLAUDE.md` is a thin tool-specific overlay on top of it.

**Six skills, each with an executable validation script** — not prose an agent can reason its way
around:

| Skill | Job | Role |
|---|---|---|
| `kpi-contract-guard` | Blocks a KPI change lacking a contract version bump | Gate |
| `threshold-decision` | Refuses a threshold without profiling evidence and a named approver | Clarifier |
| `data-profiling-runner` | Executes the 16-step profiling spec, emits the evidence report | Pipeline |
| `dq-rule-authoring` | Turns a `DQ-###` rule into a test plus audit wiring | Generator |
| `medallion-transform` | Applies the Bronze/Silver/Gold layer contracts | Domain wrapper |
| `kpi-lineage-doc` | Emits source → Gold lineage for every KPI | Generator |

**Gates run in two places.** A `.githooks/pre-commit` hook blocks secrets, raw data and
unversioned contract changes; a GitHub Actions workflow re-runs all of it, because the hook is
opt-in per clone and a guard nobody has verified is prose with extra steps.

**Adversarial evals.** `evals/` holds trajectory tests for the cases that actually matter —
*"just use 2 hours as the long-trip threshold"*, *"exclude the outliers so the average looks
better"*. They live apart from `tests/` deliberately: tests verify the deterministic parts, evals
verify the non-deterministic ones.

**What an agent may not do here:** commit a secret or raw data, approve a data-quality exception,
delete a record to improve a metric, invent a threshold, or describe a geodesic measure as road
distance. The first three are blocked mechanically rather than requested politely.

### The guardrails caught real mistakes

Not theoretical. During the Databricks build-out the gates and checks caught, among others:

- A `passenger_count_domain` value written as a list when the model reads `.min`/`.max` — dbt
  failed to compile rather than silently producing an empty `BETWEEN`.
- A contract guard reporting phantom edits to five KPIs: it read the git base with the platform's
  locale codec but the working tree as UTF-8, so every field containing `§` or `—` looked
  modified. Fixed with an explicit encoding.
- A bundle that deployed cleanly while its dashboard tables rendered as *"no fields selected"* —
  the API accepts an incomplete widget spec and stores it without error, so a round-trip check
  proves storage, never rendering.

---

## Data quality framework

15 rules in `configs/quality_rules.yml`, each with an id, an action and a test:

- **11 reject** → the row moves to `silver_trips_quarantine` with its rule id and reason
- **2 flag** → the row stays in `silver_trips` carrying a boolean (`is_duration_outlier`, …)
- **2 policy** → govern how the other rules behave

The reject/flag split *is* the design. A zero-passenger trip is suspicious, not impossible —
deleting it would change the trip count, which is KPI-001. So it is flagged and kept. Every
rejected row stays auditable, and the reconciliation test fails loudly if the totals ever stop
adding up.

## KPIs

20 KPIs defined in `configs/kpi_config.yml` as machine-readable contracts — formula, filter,
grain, dimensions, owning mart. SQL *reads* them; it never restates them, because a formula copied
into a second file is a formula that will drift.

Six thresholds shipped unset; all six are now approved and **all 20 KPIs build**. They were
resolved from the completed profiling run and approved
with recorded evidence — for example `long_trip_seconds = 3600`, chosen over P99 (3,440s) and P95
(2,104s) because it is legible to a stakeholder *and* lands on the distribution's P99 break, with
the 12,317 affected rows measured rather than estimated. Every decision, its alternatives and its
approver are in `docs/profiling/threshold-decisions.md`.

Two naming rules that are correctness rather than style: coordinate-derived measures are prefixed
`estimated_` and never called road distance or actual speed (they are geodesic, and a real route
is longer by a factor that varies), and durations are stored in seconds, presented in minutes, and
never mixed in one column.

## Dashboard

An AI/BI dashboard declared in the bundle rather than assembled by clicking, so panels review as a
diff: 21 widgets over 8 datasets — KPI counters, demand trend, hour-of-day profile, vendor
comparison, top areas and routes, data-quality detail and the quarantine breakdown. Generated from
the same SQL in `src/dashboards/queries/` by `scripts/generate_dashboard.py`.

The vendor panel shows P50 and P90 beside the mean deliberately: durations are right-skewed and
vendor trip mixes differ, so a chart comparing averages alone invites a conclusion the data does
not support.

---

## Tech stack

| Area | Tools |
|---|---|
| Platform | Databricks · serverless compute · Unity Catalog · Delta Lake |
| Transformation | dbt-core · dbt-databricks · Spark SQL |
| Ingestion & profiling | PySpark · Python |
| Deployment | Databricks Asset Bundles · dev/prod targets · declared job + dashboard |
| CI/CD | GitHub Actions · pre-commit hooks |
| Quality | dbt tests · pytest · ruff · sqlfluff |
| Contracts | YAML for schema, DQ rules and KPI definitions |

## Repository layout

```
databricks.yml        Asset Bundle — catalog, schemas, volume, job, dashboard, grants
resources/            bundle resources (catalog, jobs, dashboards, permissions)
configs/              machine-readable contracts: 11-column schema, 15 DQ rules, 20 KPIs
specs/                the spec — source of truth, with 7 BDD acceptance scenarios
src/ingestion/        Bronze loader — hashed, idempotent, append-only
src/transformations/  dbt project — Silver, the DQ split, 5 Gold marts
src/profiling/        profiling engine — 6 output tables + evidence report
src/dashboards/       dashboard queries + generated .lvdash.json
src/orchestration/    preflight workspace checks
scripts/              bundle validator, dashboard generator
tests/                32 deterministic data tests
evals/                agent trajectory + skill-trigger evals
.claude/skills/       6 skills, each with a validation script
.githooks/            pre-commit secret, raw-data and contract guard
docs/                 business contracts, profiling evidence, architecture, lineage
```

## Running it

**On Databricks** — the verified path:

```bash
cp .env.example .env                   # fill in host + token locally; .env is gitignored
python -m src.orchestration.preflight  # connection, schemas, volume, write access
databricks bundle deploy --target dev --var warehouse_id=<id>
databricks bundle run nyc_taxi_pipeline --target dev
```

**Locally**, against a synthetic fixture carrying 15 planted defect classes — no Databricks
account, same Spark SQL engine:

```bash
export SPARK_CONF_DIR="$PWD/conf"
python tests/fixtures/make_fixture.py --out data/fixture_trips.csv
python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
python -m src.transformations.run --target local --allow-withheld
pytest tests/
```

Needs a JDK 17/21 that includes `jdk.incubator.vector` — PySpark 4 requires that module and some
bundled runtimes omit it. On Windows, WSL2 is the route that works.

Enable the guard once per clone — required, and never bypass it with `--no-verify`:

```bash
git config core.hooksPath .githooks
```

## Design decisions worth knowing

- **`--allow-withheld` exists because the gate would otherwise deadlock.** Profiling produces the
  evidence the thresholds need, but profiling runs *after* the gate. The flag builds the unblocked
  KPIs and names what it withheld, so the first run can happen at all.
- **Bronze uses a `source_hash` check, not `MERGE`.** MERGE updates rows in place, which is
  precisely what an append-only contract forbids.
- **Gold marts live in their own schema** so `SELECT` on `gold` is a grant that actually means
  "can read the marts and nothing upstream".
- **Local Bronze is Delta too**, so the local format matches production rather than only the SQL.

## Known gaps

Tracked openly rather than quietly:

- `resources/permissions.yml` uses a top-level `resources.grants` block that Databricks Asset
  Bundles do not support, so the least-privilege grants are documented but **not deployed**.
- `vendor_domain` (DQ-003) is still `TBD_PENDING_PROFILING`. Profiling observed exactly `[1, 2]`
  covering 100% of rows, but DQ-003 *rejects*, so it awaits an explicit approval rather than an
  inferred one.
- Deploying in `mode: development` name-prefixes the bundle's schema resources, leaving orphan
  `dev_<user>_*` schemas that nothing reads.

## Source data

Kaggle — *NYC Taxi Trip Duration*. Public, no PII. Never committed: the dataset is gitignored and
the pre-commit hook blocks it. See `data/README.md` for acquisition and hashing.
