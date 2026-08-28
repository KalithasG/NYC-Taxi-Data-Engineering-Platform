# KPI Contract Changelog

Every change to a KPI's meaning is recorded here. KPI contract §20 requires seven fields per
change; `.claude/skills/kpi-contract-guard/scripts/check_kpi_contract.py` verifies all seven are
present before a commit touching `configs/kpi_config.yml` is allowed through.

**Current contract version: 1.2** — one approved change (v1.2, the Gold schema relocation).
v1.1 is still drafted and unsigned. Version numbers are labels, not a dense sequence, so the
gap is expected: v1.1 can still be approved later without renumbering anything.

## Why this file exists

A KPI whose formula shifts without a record is worse than a broken one. A broken KPI throws an
error; a redefined one keeps rendering, keeps passing tests, and quietly stops meaning what last
quarter's number meant. This changelog is what makes the two distinguishable after the fact.

## Version semantics (contract §20)

| Version | For |
|---|---|
| **1.1+** | Clarifications that do **not** alter the KPI's meaning — wording, added dimension documentation, a corrected typo in a description |
| **2.0+** | Breaking changes: formula, population/filter, grain, a threshold change that materially alters interpretation, or a dimension change affecting historical comparability |

If you are unsure which applies, ask: *would a chart of this KPI before and after the change be
directly comparable?* If no, it is a major version.

## Entry format

Each entry is a `## v<version>` heading, then one `### <KPI-ID> — <short title>` per affected KPI.
All seven fields are required — the guard script checks for each by name.

```markdown
## v2.0 — YYYY-MM-DD

### KPI-002 — Average Trip Duration now excludes duration outliers
- **Old:** AVG(trip_duration) over all valid trips
- **New:** AVG(trip_duration) over valid trips where is_duration_outlier = false
- **Reason:** <the business problem this solves — not "it looks better">
- **Effective:** YYYY-MM-DD
- **Impact:** <who is affected; whether historical figures remain comparable; expected magnitude>
- **Migration:** <what consumers must do; whether history is rebuilt or left as-is>
- **Approved by:** <a named human — never an agent>
```

## Pending — not yet approved

### v1.1 (draft) — remove KPI-021..024, model performance metrics

Tracked as spec **OQ-1**. The KPI contract v1.0 document defined 24 KPIs, four of which measured a
predictive model rather than the taxi operation. Those four are out of scope for this platform and
have been removed from the contract (now §12, which records the exclusion).
`configs/kpi_config.yml` already held the 20-KPI scope, so the contract owes itself this record.

This is **deliberately left unapproved.** Filling in an approver would be exactly the forgery the
guard exists to prevent. A human should review and sign it off, at which point it moves into the
list above with `contract_version` bumped to 1.1.

- **Old:** KPI-021..024 (RMSLE, MAE, RMSE, P90 Absolute Error) defined in the contract
- **New:** removed from the contract; recorded as out of scope in §12
- **Reason:** they measure a model, not the taxi operation — a different grain (model run vs
  trip), lifecycle and audience. Mixing them in makes "what does this platform measure?"
  unanswerable.
- **Effective:** _pending approval_
- **Impact:** none — never implemented; no mart, model or consumer depends on them
- **Migration:** none required
- **Approved by:** _pending_

## Approved changes

## v1.2 — 2026-08-27

### Gold marts relocated into a `gold` Unity Catalog schema

Affects the `mart` field of every KPI in the contract:
KPI-001, KPI-002, KPI-003, KPI-004, KPI-005, KPI-006, KPI-007, KPI-008, KPI-009, KPI-010,
KPI-011, KPI-012, KPI-013, KPI-014, KPI-015, KPI-016, KPI-017, KPI-018, KPI-019, KPI-020.

`mart` is a semantic field under §20, so the move is recorded here even though no KPI's value
changes. It is one relocation applied uniformly, not twenty separate decisions, so it is recorded
as one entry rather than twenty near-identical ones.

Raised by an external Databricks review recommending one Unity Catalog schema per medallion
layer. The layer previously existed only in the table name, and a name is not a securable — so
"analysts read Gold and nothing else" could not be expressed. `resources/catalog.yml` already
declared the four schemas and `resources/permissions.yml` already granted against them; this
change makes the code match what the bundle deploys.

- **Old:** `gold_trip_performance`, `gold_demand_metrics`, `gold_geographic_metrics`,
  `gold_vendor_performance`, `gold_data_quality` — all sharing the one `nyc_taxi_dev` schema
- **New:** `gold.trip_performance`, `gold.demand_metrics`, `gold.geographic_metrics`,
  `gold.vendor_performance`, `gold.data_quality`
- **Reason:** enables least-privilege grants per layer (SECURITY_CHECKLIST Pillar 2). An analyst
  who can read Silver can publish a number that bypassed the KPI contract; with the marts in
  their own schema, `SELECT` on `gold` alone is now a grant that actually means that.
- **Effective:** 2026-08-27
- **Impact:** no KPI value changes — a relocation, not a redefinition. No formula, filter, grain
  or dimension moved, and figures before and after are directly comparable, which is why this is
  a minor version. Every consumer that names a mart was updated in the same change: the six
  dashboard queries, both dbt singular tests, `models/gold/schema.yml`, both pytest suites and
  the lineage document. Note the consequence for grants: dashboard queries 01 and 06 also read
  `silver_trips`, so an analyst holding only the `gold` grant cannot run them as written.
- **Migration:** rebuild in place. Nothing was published, so no archived numbers move. The
  superseded `nyc_taxi_dev.gold_<mart>` tables are not renamed — the rebuild writes the new
  location and the old copies must be dropped, or a stale consumer reads figures that stop
  updating while still rendering. Local and
  Databricks both route via `macros/schema_routing.sql`, which uses a custom schema verbatim
  instead of dbt's default `<target>_<custom>` prefixing — without it the models would land in
  `nyc_taxi_dev_gold`, which no grant covers.
- **Approved by:** Kalithas G (kalithas878@gmail.com)
