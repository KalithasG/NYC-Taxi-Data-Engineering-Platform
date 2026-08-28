---
name: kpi-contract-guard
description: "Guards the KPI definitions in configs/kpi_config.yml against silent drift. Use this whenever a change would touch what a KPI MEANS — its formula, filter, population, grain, dimensions or owning mart — or when someone asks to change, adjust, redefine, tweak, fix, correct or 'improve' a metric, to exclude or include rows in a KPI, to add or remove a KPI, or to make a number look different. Also use when editing configs/kpi_config.yml or any gold_* model, when a KPI value looks wrong and the fix under discussion is changing the definition, and when adding a model-performance metric (KPI-021..024) that is out of scope for this platform. Trigger even when the request sounds small ('just exclude outliers from the average') — small-sounding definition changes are exactly the ones that ship unrecorded."
---

# KPI Contract Guard

A KPI that breaks throws an error and gets fixed. A KPI that gets *redefined* keeps rendering,
keeps passing its tests, and quietly stops meaning what it meant last quarter. Nobody notices for
months, and by then nobody can say which numbers were computed under which definition.

That is the failure this guards against. It is not bureaucracy — it is the difference between a
metric and a rumour.

## Start with the script

Run it before reasoning about anything. It answers "did a definition actually change?"
deterministically, which is more reliable than reading a diff:

```bash
python3 .claude/skills/kpi-contract-guard/scripts/check_kpi_contract.py
python3 .claude/skills/kpi-contract-guard/scripts/check_kpi_contract.py --staged   # pre-commit view
```

It compares `configs/kpi_config.yml` against `HEAD` and reports:

- **Semantic changes** — `name`, `formula`, `filter`, `grain`, `dimensions`, `mart`,
  `threshold_ref`. These change meaning and need a version bump.
- **Editorial changes** — `priority`, notes, caveats. Reported, never blocking.
- **Scope violations** — KPI-021..024 reintroduced (model metrics, out of scope — contract §12).
- **Consistency** — `kpi_count` matching the actual number of KPIs.

Exit 0 means clean or properly versioned. Exit 1 means something needs the treatment below.

The same script runs in `.githooks/pre-commit`, so an unversioned change cannot be committed even
if this skill never fires. Do not work around it with `--no-verify` — that is denied in
`.claude/settings.json` for this reason.

## When the gate stops you

The script tells you *that* a definition changed. It cannot tell you whether the change is
**right**, and that is the part worth thinking about.

### 1. Ask whether the definition should change at all

Often the honest answer is no. Watch for these, because they are the common ones:

| What was asked | What is usually going on |
|---|---|
| "Exclude outliers so the average looks better" | The mean is being asked to hide a real long tail. KPI-003 (median) and KPI-004 (P90) already exist for exactly this — that is *why* they exist. |
| "This number seems too high" | A data-quality problem upstream, not a definition problem. Check the DQ rules and quarantine table first. |
| "Filter to trips under an hour" | An unapproved threshold wearing a filter's clothing. That is `threshold-decision`'s job, not a contract change. |
| "Add RMSLE to the Gold layer" | Out of scope — KPI-021..024 measure a model, not the operation (contract §12). |

If the underlying need is served by an existing KPI or a new one, say so. Adding KPI-021 is a
contract change; computing the median instead of the mean is just using the contract correctly.

### 2. Classify the change

Read `references/contract-versioning.md` for the full rules. The short test:

> Would a chart of this KPI spanning the change be directly comparable across it?

- **Yes** → clarification → `contract_version` 1.1+
- **No** → breaking → `contract_version` 2.0+

Formula, population/filter, grain and dimension changes are almost always breaking, because they
alter historical comparability even when the new definition is better.

### 3. Write the changelog entry

Add it to `docs/business/kpi-changelog.md` under a `## v<new-version>` heading, with a
`### <KPI-ID> — <title>` block carrying all seven fields: **Old, New, Reason, Effective, Impact,
Migration, Approved by**. The script checks each by name.

Two fields carry the real weight:

- **Impact** — who is affected, whether history stays comparable, roughly how much the number
  moves. "Values will shift" is not an impact assessment; "median duration drops ~8% because
  trips over the P99 no longer count, so Q1-Q2 charts are not comparable" is.
- **Approved by** — a named human. Propose the entry; never sign it. Strategy doc §28 lists
  changing KPI definitions among the things an agent must not do independently, and this is the
  point where that rule becomes concrete.

### 4. Bump and re-run

Update `contract_version` in `configs/kpi_config.yml`, then re-run the script. It will confirm the
bump and the matching entry, or name exactly what is still missing.

## Where the definitions live

`configs/kpi_config.yml` is authoritative — the SQL, the marts and the dashboards all derive from
it. `docs/business/kpi-data-contract.md` is the upstream source document and explains *why* each
KPI exists. When the two disagree, the YAML is what runs and the discrepancy is a bug worth
raising rather than quietly reconciling.
