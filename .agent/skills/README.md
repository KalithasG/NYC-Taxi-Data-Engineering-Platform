# Planned Skills — NYC Taxi Data Engineering Platform

**Stage 4** of the agentic-engineering workflow — the cross-tool plan for all six skills.

> **Canonical files live in `.claude/skills/<name>/`, not here.** Claude Code only discovers project
> skills at `.claude/skills/<name>/SKILL.md`; a skill in this directory would never load, which for
> a gate means it would never fire. This file stays as the tool-agnostic plan and the rationale for
> the build order; the working skills are one directory over.

Skills are the unit of improvement: cheap metadata always in context, body loaded only on trigger.
That is why capability here scales without bloating every prompt.

---

## The six skills

Each maps to a rule that `docs/business/` already demands but that today exists only as prose in a
document the agent may or may not read. A skill turns it into a habit that fires on its own.

### 1. `kpi-contract-guard` — build order 1 · **BUILT** → `.claude/skills/kpi-contract-guard/`
**Job:** Block any change to a KPI formula, filter, grain or dimension set that does not carry a
matching contract version bump.
**Role:** Reviewer & Gate.
**Trigger on:** editing `configs/kpi_config.yml`; editing a `gold_*` model; the phrases "change the
KPI", "adjust the formula", "redefine", "tweak the metric".
**Enforces:** KPI contract §20 — every change needs KPI ID, old definition, new definition, reason,
effective date, impact assessment, migration requirement.
**Why first:** it is the guardrail against the single worst failure mode here — business
definitions drifting silently while every dashboard keeps rendering.

### 2. `threshold-decision` — build order 2 · **BUILT** → `.claude/skills/threshold-decision/`
**Job:** Refuse to set any `TBD_PENDING_PROFILING` threshold without percentile evidence, affected
record counts, and an impact statement; then walk the profiling §31 decision tree.
**Role:** Inversion & Recovery (clarifier).
**Trigger on:** "set the threshold", "what should the cutoff be", "long trip", "low speed",
"outlier limit"; any edit to `thresholds:` in `configs/kpi_config.yml`.
**Enforces:** KPI contract §18, profiling spec §31.
**Why second:** an invented threshold is invisible business logic — it looks like a number and
behaves like an unreviewed policy decision.

### 3. `data-profiling-runner` — build order 3 · **BUILT** → `.claude/skills/data-profiling-runner/`
**Job:** Execute the 16-step profiling order from profiling spec §34 and emit the six `profile_*`
tables plus `docs/profiling/profiling-report.md`.
**Role:** Pipeline.
**Trigger on:** "profile the data", "run profiling", "what does the data look like", a new source
file hash.
**Enforces:** profiling spec §29 output tables, §33 success criteria.

### 4. `dq-rule-authoring` — build order 4 · **BUILT** → `.claude/skills/dq-rule-authoring/`
**Job:** Turn one `DQ-###` entry from `configs/quality_rules.yml` into an executable test plus its
quarantine/audit wiring.
**Role:** Generator.
**Trigger on:** "add a quality rule", "implement DQ-", "validate this column".
**Enforces:** contract §14; the flag-vs-reject distinction; DQ-015 auditability.

### 5. `medallion-transform` — build order 5 · **BUILT** → `.claude/skills/medallion-transform/`
**Job:** Apply the Bronze/Silver/Gold conventions to any new model — raw immutable, silver
deterministic, gold idempotent, naming, `estimated_` prefixing.
**Role:** Domain Context Wrapper.
**Trigger on:** creating or editing any model under `src/transformations/`; "add a silver model",
"build the gold mart".
**Enforces:** contract §16 engineering acceptance criteria; spec §4 layer contracts.

### 6. `kpi-lineage-doc` — build order 6 · **BUILT** → `.claude/skills/kpi-lineage-doc/`
**Job:** Emit the source column → silver derived → transformation → gold metric → consumer lineage
block for a KPI.
**Role:** Generator.
**Trigger on:** "document lineage", "where does this number come from", adding a KPI to a mart.
**Enforces:** contract §17 — every Gold KPI must have lineage.

---

## Build order rationale

`kpi-contract-guard` and `threshold-decision` are gates; the rest are producers. Gates ship first,
because a producer that runs without its gate can quietly do damage that is expensive to detect
later. Everything else follows the pipeline's own order: profile → validate → transform → document.

## Where they live

`.claude/skills/<name>/SKILL.md`, each with optional `scripts/`, `references/`, `assets/`.

The two built gates each pair a **deterministic script** with a **judgement layer**. The script is
the gate — it also runs in `.githooks/pre-commit`, so it holds whether or not the skill triggers.
The skill body is what makes the outcome good once the gate stops you:

| Skill | Script | Role of the script | In pre-commit |
|---|---|---|---|
| `kpi-contract-guard` | `check_kpi_contract.py` | Blocks unversioned KPI changes | yes |
| `threshold-decision` | `check_thresholds.py` | Blocks evidence-free thresholds | yes |
| `medallion-transform` | `check_layer_contracts.py` | Lints layer contracts + BDD-07 wording | yes |
| `data-profiling-runner` | `check_profiling_complete.py` | Validates a run against spec §33 | no |
| `dq-rule-authoring` | `check_dq_rules.py` | Validates rule structure, reports coverage | no |
| `kpi-lineage-doc` | `check_lineage.py` | Checks + scaffolds lineage blocks | no |

Three scripts are wired into `.githooks/pre-commit` and three are not, and the split is
deliberate. A gate belongs in the hook when it can pass on the current repo state. The other
three are coverage checks against `src/` and `tests/`, which are empty — wiring them now would
block every commit from day one, and a gate people have to disable is worse than no gate.
Turn them on (`--strict`) once the code they check exists.

## Evaluation

Every skill needs trigger evals before it is trusted — **the trigger is the first gate**; if the
description does not route correctly, nothing else about the skill matters. One rephrasing and one
negative boundary case per positive trigger, in `evals/`. See `EVAL_PLAN.md` §2.

Written: `evals/triggers/kpi-contract-guard.json` and `threshold-decision.json` (7 cases
each), `evals/triggers/remaining-skills.json` (5 cases each for the other four), plus
`evals/adversarial/A1-invent-threshold.md` and `A3-change-kpi-formula.md`.

With six skills installed the dominant risk shifts from *under-triggering* to *mis-routing* —
firing `dq-rule-authoring` on a question that belongs to `threshold-decision`, say. Most of the
negative cases are therefore cross-skill routing tests rather than plain non-triggers. These
specify the routing; they have not been run against a live session yet.
