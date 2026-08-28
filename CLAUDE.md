# CLAUDE.md — Claude Code overlay

**Read `AGENTS.md` first.** It holds the shared truth for every agent in this repo: the five rules,
the layer contracts, the conventions and the forbidden actions. This file only adds Claude
Code-specific notes on top.

## Claude Code specifics

- **Plan mode for anything structural.** New pipeline layer, new Gold mart, or a change touching
  `configs/*.yml` → plan first, get approval, then build.
- **Hooks are configured in `.claude/settings.json`.** They run the formatter after edits. If a
  hook fires and fails, fix the cause — do not disable the hook.
- **The pre-commit guard lives in `.githooks/pre-commit`** and is wired via `core.hooksPath`.
  Enable it once per clone with `git config core.hooksPath .githooks` (see `README.md`).
  Never commit with `--no-verify`.
- **Read the YAML before writing SQL.** `configs/kpi_config.yml` already holds every KPI formula,
  filter and grain. Reproducing one from memory is how definitions silently drift.

## Fast orientation

| Question | File |
|---|---|
| What are we building and why? | `specs/nyc-taxi-data-engineering-platform-spec.md` |
| What does "correct" mean? | spec §6 (BDD scenarios) → `EVAL_PLAN.md` |
| What is a KPI's exact formula? | `configs/kpi_config.yml` |
| What makes a row invalid? | `configs/quality_rules.yml` |
| Why is this threshold blank? | `docs/profiling/threshold-decisions.md` |
| What am I not allowed to do? | `AGENTS.md` → Forbidden actions |
| Why did the commit get blocked? | Run the gate scripts in `.claude/skills/*/scripts/` |
| What do I do next? | `PROJECT_PLAN.md` → Immediate next action |
