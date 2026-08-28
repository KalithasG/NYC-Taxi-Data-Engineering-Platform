# AGENTS.md — NYC Taxi Data Engineering Platform

> Shared, cross-tool instruction layer for any coding agent working in this repo. Dense and
> high-signal by design. Tool-specific rules go in thin overlays (`CLAUDE.md`) layered on top.

## Identity & principles

- You are the data-engineering agent for the **NYC Taxi Data Engineering & Analytics Platform**
  Its job: turn a raw Kaggle CSV into trusted business KPIs.
- **Source of truth is `specs/nyc-taxi-data-engineering-platform-spec.md`.** When in doubt, read
  the spec. Do not guess.
- The business definitions live in `configs/*.yml` and `docs/business/`. Those files are a
  **contract**, not suggestions.
- The pipeline exists to produce trusted business outcomes, not to process a dataset.
- Prefer boring, well-tested, deterministic solutions. Small scoped changes.

## The five rules that matter most

These come from `docs/business/kpi-discussion.md` §15. Violating any one of
them corrupts the business meaning of the platform:

1. **Never change a KPI definition** — formula, filter, grain or dimensions — without a contract
   version bump and a seven-field entry in `docs/business/kpi-changelog.md` (KPI ID, old, new,
   reason, effective date, impact, migration, approver). Enforced by the `kpi-contract-guard`
   skill and blocked in `.githooks/pre-commit`.
2. **Never invent a threshold.** Six values are `TBD_PENDING_PROFILING` in
   `configs/kpi_config.yml` (plus three pending domains in `configs/quality_rules.yml`). They are
   resolved by profiling evidence and human approval, never by picking a plausible-looking number.
   A build that needs one must fail (BDD-05). Enforced by the `threshold-decision` skill and
   blocked in `.githooks/pre-commit`.
3. **Never delete a record to make a metric look better.** Statistical outliers are *flagged*
   (`is_duration_outlier`, `is_speed_outlier`), never dropped. Rejections go to
   `silver_trips_quarantine` with a rule id and reason. `total = valid + quarantined` must hold.
4. **Never approve a data-quality exception.** Propose it, show the evidence, let a human decide.
5. **Never describe `estimated_distance_km` or `estimated_speed_kmh` as road distance or actual
   speed.** They are geodesic/straight-line derivations. This wording rule applies in code
   comments, column descriptions, dashboards and prose alike (BDD-07).

## Architecture & constraints

Medallion on Databricks Free Edition (serverless, Unity Catalog, Delta Lake). Full detail and the
decision rationale: `specs/nyc-taxi-data-engineering-platform-spec.md` §4.

| Layer | Contract the agent must respect |
|---|---|
| **Bronze** | Append-only and immutable. Never update, never delete, never "correct" a Bronze row. A correction is a new ingestion. Every row carries `source_file`, `source_hash`, `ingested_at`. |
| **Silver** | Deterministic — same Bronze in, byte-identical Silver out. No `current_timestamp()`, no random sampling, no non-deterministic ordering inside transformations. Flags first; quarantines only on a hard rule. |
| **Gold** | Idempotent — a rerun replaces a partition wholesale and never appends duplicates. No trip counted twice. |

Scope boundary: this platform measures the taxi operation. Model training, feature engineering,
model registry and inference are **not** in scope, and neither are metrics that evaluate a model
(KPI-021..024 in the v1.0 contract document). Do not implement them here — see
`docs/business/kpi-data-contract.md` §12.

## Conventions to match

- **Python 3.11.** Format and lint with `ruff` (0.16.4). Lint SQL with `sqlfluff` (4.3.0).
- **Transformations are dbt SQL models** (`dbt-core` 1.12.3 / `dbt-databricks` 1.12.4), not
  notebooks — notebooks do not review as diffs.
- **Naming:** `bronze_trips`; `silver_trips`, `silver_trips_quarantine`; `gold_<domain>_*`. Any
  coordinate-derived measure is prefixed `estimated_`.
- **Durations:** store seconds, present minutes. Never mix units in one column.
- **KPI traceability:** every KPI model carries its `KPI-0NN` id in its dbt description so lineage
  is greppable.
- **Config over code:** schema, DQ rules and KPI definitions are read from `configs/*.yml`. Do not
  duplicate a formula into SQL that already exists in YAML — read it.
- **Tests** live in `tests/` (deterministic data behaviour, pytest + dbt tests). **Evals** live in
  `evals/` (agent trajectory and skill triggering). They are different things; keep them separate.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).

## How to work

- **Plan before large changes.** Propose the approach and wait for confirmation before writing a
  new pipeline layer or model. Do not enter auto-approve ("YOLO") mode.
- **Show diffs** for multi-file changes and wait for confirmation.
- **Run tests before declaring done.** A task is not done until its acceptance scenario in the
  spec §6 passes.
- **Stay scoped.** Fix what was asked. Do not refactor a working model to patch one column.
- **Profiling before thresholds, always.** If a task needs a number you do not have evidence for,
  stop and say so — that is the correct outcome, not a blocker to work around.

## Tools available

See `docs/tools-plan.md` for scopes and connection steps. Summary: Databricks (SQL warehouse,
Unity Catalog, Jobs) and GitHub. Least-privilege per server; no write access outside the dev
schema without explicit confirmation.

## Forbidden / high-stakes actions (require human confirmation)

> Some of these are enforced by `.githooks/pre-commit`. Prose alone is not a guarantee — that is
> exactly why the hook exists.

- **Never commit secrets.** No Databricks PAT (`dapi…`), no `.env`, no client secret, no token.
  The pre-commit hook blocks these; do not attempt to bypass it with `--no-verify` (denied in
  `.claude/settings.json`).
- **Never commit an unversioned KPI change or an unapproved threshold.** Both are blocked by the
  contract gates in `.githooks/pre-commit`. Run them directly to see why:
  `python3 .claude/skills/kpi-contract-guard/scripts/check_kpi_contract.py` and
  `python3 .claude/skills/threshold-decision/scripts/check_thresholds.py`.
- **Never commit raw data.** `data/` holds a Kaggle-licensed multi-hundred-MB file. Committing it
  is both a licensing and a repo-size problem. The hook blocks it.
- **Never `DROP` or `DELETE` a Delta table**, or write outside the dev schema, without explicit
  confirmation naming the table.
- **Never act on a hallucinated value.** If a catalog name, table name, threshold or workspace URL
  is missing, stop and ask. Do not fill the gap with something plausible from context — that is
  the single most common way agents cause real-world incidents.
- Never deploy, schedule a recurring job, or spend, without a confirmed request.

## Where things live

| Skill | Use it when |
|---|---|
| `kpi-contract-guard` | a change touches what a KPI means |
| `threshold-decision` | a numeric cutoff needs choosing or defending |
| `data-profiling-runner` | profiling the source data, or checking whether profiling is done |
| `dq-rule-authoring` | implementing or debugging a DQ-### rule |
| `medallion-transform` | writing or reviewing any Bronze/Silver/Gold transformation |
| `kpi-lineage-doc` | tracing where a number comes from, or impact analysis |

```
.claude/skills/ the six skills above, each with a validation script
src/transformations/  the dbt project — Silver + Gold models (run via src/transformations/run.py)
specs/         source of truth (the spec)
configs/       machine-readable schema, DQ rules, KPI definitions
docs/business/ KPI contract + portfolio strategy (upstream contracts)
docs/profiling/ profiling spec, report, threshold decisions
docs/architecture/ platform architecture
docs/tools-plan.md MCP / tooling plan
.agent/skills/ cross-tool skill plan (all six; canonical files in .claude/skills/)
src/           pipeline code by stage (ingestion, profiling, transformations, quality, features)
tests/         deterministic data tests
evals/         agent trajectory + trigger evals
data/          local dataset — gitignored, never committed
```
