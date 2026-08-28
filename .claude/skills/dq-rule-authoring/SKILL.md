---
name: dq-rule-authoring
description: "Implements the data-quality rules DQ-001..DQ-015 from configs/quality_rules.yml as executable tests with quarantine and audit wiring. Use this whenever adding, implementing, changing or debugging a data-quality rule, validation, or check — null checks, uniqueness, duplicate handling, timestamp ordering, coordinate plausibility, domain validation, derived-field sanity — or when asked to validate a column, quarantine bad rows, make invalid records auditable, or work out whether a record should be rejected or merely flagged. Also use when a DQ rule has no test, when the valid and quarantined counts do not reconcile, and when someone proposes dropping or filtering rows to fix a metric."
---

# DQ Rule Authoring

Fifteen rules, and the important distinction between them is not what they check but what they
*do* to a failing row:

| Action | Effect | Count |
|---|---|---|
| **reject** | Row leaves the valid population, lands in `silver_trips_quarantine` with a reason | 11 |
| **flag** | Row **stays** in the valid population, carries a boolean column | 2 |
| **policy** | Not a row predicate — a pipeline behaviour that must hold | 2 |

Getting this wrong in the permissive direction lets bad rows into KPIs. Getting it wrong in the
strict direction is worse and much harder to notice: the metric looks cleaner, and the discarded
rows are gone.

## Inspect before implementing

```bash
python3 .claude/skills/dq-rule-authoring/scripts/check_dq_rules.py            # validate + coverage
python3 .claude/skills/dq-rule-authoring/scripts/check_dq_rules.py --rule DQ-009
python3 .claude/skills/dq-rule-authoring/scripts/check_dq_rules.py --strict   # fail on uncovered rules
```

Structural validation is always strict — a `reject` rule without a `quarantine_reason` is
unauditable and fails immediately. Coverage is advisory until `tests/data_quality/` exists, then
switch on `--strict` in CI.

`--rule` prints one rule's implementation contract, including whether its parameter is still
`TBD_PENDING_PROFILING`. Four rules are in that state (DQ-003, DQ-008, DQ-009, DQ-010) — implement
their *structure*, but the value comes from `threshold-decision`, never from you.

## Reject or flag?

The governing principle is profiling spec §2: **flag first, reject only on a hard business or
data-integrity violation.** An outlier is not automatically a bad record.

Reject when the record is **logically impossible** — a dropoff before its pickup, a null primary
key, a negative duration, a negative derived distance. There is no interpretation under which the
row is valid.

Flag when the record is **unusual but possible** — an anomalous passenger count, an odd
store-and-forward value, a very long trip. Someone may need to look; nobody should lose the row.

The two extremes both cost you something real: a rejected valid row is data you silently lost, and
an accepted impossible row corrupts every aggregate it touches. When genuinely unsure, flag and
say so — a flag is recoverable, a rejection is not.

## What every reject rule must produce

DQ-015 requires that no rejection is silent. Concretely:

1. The row is written to `silver_trips_quarantine` with its **rule id** and **quarantine_reason**.
2. `total_records == valid_records + quarantined_records` holds after every run.
3. The counts feed KPI-018/019/020.

That reconciliation is the test worth writing first. If it holds, rows cannot vanish; if it does
not, something is dropping data and no amount of rule-level testing will find it.

## Two rules that trip people up

**DQ-002 (duplicates).** Deduplication happens *before* aggregation, but KPI-020 reports the
**original** duplicate count. So the audit table must capture the count before dedup — otherwise
the metric reads zero forever and looks like a clean dataset. Classify per profiling §26: exact
duplicate → dedupe; same id + identical payload → dedupe; same id + **conflicting** payload →
quarantine for review, never silently pick one.

**DQ-014 (outliers).** This is a policy, not a predicate. It forbids a transformation that deletes
rows on a percentile or IQR condition. If you find yourself writing `WHERE trip_duration < ...` in
a Silver model, that is the rule being violated — the correct shape is a flag column
(`is_duration_outlier`, `is_speed_outlier`) that Gold can filter on when a specific KPI wants it.

## Writing the test

Tests live in `tests/data_quality/`, named for the rule. Reference the rule id in the test so the
coverage checker can find it. Each rule wants three cases:

- a row that **passes** the predicate
- a row that **fails** it, asserted to land in quarantine with the right reason (or to carry the
  right flag, for a flag rule)
- the **reconciliation**: valid + quarantined equals the input count

Read thresholds and domains from `configs/quality_rules.yml` at runtime. Hard-coding a bound into a
test duplicates the contract, and the copy will drift.

Further detail, per-rule: `references/rule-implementation.md`.
