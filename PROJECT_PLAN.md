# Project Plan — NYC Taxi Data Engineering Platform

**Tier:** structured · **Platform:** Databricks Free Edition · **Generated:** 2026-08-27

> One-page roadmap tying the Agentic Engineering stages into a sequence. Each milestone names
> what it verifies, so "done" always means "verified", not "seems to work".

## Where this sits on the spectrum

**Structured tier.** Public Kaggle data, no PII, no money, no production traffic — full
production rigor would be over-engineering. Two things are nonetheless treated at production
depth, because their failure cost does not scale down with the data's sensitivity:
**credential handling** (a leaked Databricks token is a real incident) and **business-definition
integrity** (a silently changed KPI destroys the platform's whole purpose).

## Artifacts produced

| Artifact | Purpose |
|---|---|
| `specs/nyc-taxi-data-engineering-platform-spec.md` | The blueprint — source of truth |
| `AGENTS.md` + `CLAUDE.md` | Instruction layer for any coding agent |
| `configs/{schema,quality_rules,kpi_config}.yml` | Machine-readable contracts (11 cols, 15 rules, 20 KPIs) |
| `docs/business/` | KPI contract + portfolio strategy (upstream, version-controlled) |
| `docs/profiling/` | Profiling spec + report/threshold stubs |
| `docs/architecture/data-platform-architecture.md` | Medallion design on Databricks |
| `docs/tools-plan.md` | MCP / tooling plan with least-privilege scopes |
| `.claude/skills/` | All six skills, each with a validation script |
| `docs/architecture/kpi-lineage.md` | Lineage for all 20 KPIs (contract §17) |
| `.agent/skills/README.md` | Cross-tool plan for all six skills |
| `SECURITY_CHECKLIST.md` | 7-pillar envelope |
| `EVAL_PLAN.md` | Tests + evals + observability |
| `.githooks/pre-commit` | Working secret/data guard (9/9 tests pass) |

## Sequenced roadmap

| # | Milestone | Builds | Verified by | Status |
|---|---|---|---|---|
| 0 | Calibrate & scaffold | this plan, repo tree | Tier chosen, structure in place | **done** |
| 1 | Spec locked | `specs/…` | Acceptance scenarios reviewed by a human | **done — awaiting review** |
| 2 | Harness configured | `AGENTS.md`, hooks | Hook blocks a planted secret; agent respects rules on a dry run | **done (hook verified)** |
| 3 | Tools wired | MCP / SDK access to Databricks | Agent lists tools and runs `SELECT 1`; scopes least-privilege | next |
| 4 | **Profiling run** | `profile_*` tables, `profiling-report.md` | All 19 boxes in profiling spec §33 ticked | **engine built + verified; the RUN needs the dataset** |
| 5 | Thresholds approved | `threshold-decisions.md`, contract v1.1 | Zero `TBD_PENDING_PROFILING` remain in `kpi_config.yml` | blocked by 4 |
| 6 | Bronze pipeline | `src/ingestion/` | BDD-01 passes | **done — verified locally** |
| 7 | Silver + DQ framework | `src/transformations/models/silver/` | BDD-02, BDD-03, BDD-06 pass | **done — verified locally** |
| 8 | Gold KPI marts | 5 marts, 18 of 20 KPIs | BDD-04, BDD-05 pass | **done — 18 built, KPI-016/017 withheld pending thresholds** |
| 9 | First skills built | `.claude/skills/…` | Trigger evals A1-A7 pass | **done — all 6 built** |
| 10 | Dashboard | AI/BI executive view | BDD-07 holds on every label | **queries built + verified; panels await a workspace** |

Milestone 4 is the real gate. Milestones 5, 7 and 8 all depend on evidence that does not exist
yet, and the entire threshold-governance design exists to stop that gap being filled by guesswork.

## Immediate next action

**Acquire the dataset and run the profiling specification against it** (profiling spec §38).

The pipeline itself is now built and verified against a synthetic fixture — see
`docs/architecture/databricks-setup.md`. Real data is what turns 18 verified KPIs into 20
and replaces the fixture's numbers with the operation's.

Concretely: `data/README.md` → download → record SHA256 → work through the 16 steps in profiling
spec §34 → produce `docs/profiling/profiling-report.md` → propose thresholds with evidence in
`docs/profiling/threshold-decisions.md`.

Everything downstream is blocked on this, by design. The profiling spec's own closing line:
*"Do not finalize KPI thresholds before this profiling run."*

## Planned skills (from Stage 4)

| Skill | Job | Role | Build order |
|---|---|---|---|
| `kpi-contract-guard` | Block KPI changes without a contract version bump | Reviewer/Gate | 1 — **built** |
| `threshold-decision` | Refuse thresholds without profiling evidence | Clarifier | 2 — **built** |
| `data-profiling-runner` | Run profiling §34's 16 steps, emit report | Pipeline | 3 — **built** |
| `dq-rule-authoring` | Turn a DQ-### rule into a test + audit wiring | Generator | 4 — **built** |
| `medallion-transform` | Apply Bronze/Silver/Gold layer contracts | Domain Wrapper | 5 — **built** |
| `kpi-lineage-doc` | Emit source→Gold lineage per KPI | Generator | 6 — **built** |

All six built. Gates before producers — see `.agent/skills/README.md` for the rationale,
the trigger phrasings, and which scripts are wired into pre-commit.
