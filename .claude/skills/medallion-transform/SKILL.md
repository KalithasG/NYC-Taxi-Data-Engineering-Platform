---
name: medallion-transform
description: "Applies the Bronze/Silver/Gold layer contracts when writing or reviewing any transformation in this repo — raw immutable, Silver deterministic, Gold idempotent — plus the naming and wording rules for coordinate-derived measures. Use this whenever creating, editing or debugging a dbt model, SQL transformation, ingestion job or pipeline stage; when adding a bronze_, silver_ or gold_ table; when deciding where a piece of logic belongs; and when a rerun produces different numbers, double-counts rows, or a transformation needs deduplication, backfilling or correcting. Also use before labelling any distance or speed column, since coordinate-derived measures are geodesic and must never be presented as actual road distance."
---

# Medallion Transform

Three layer contracts. Each exists because of a specific failure that is cheap to prevent and
expensive to discover later.

| Layer | Contract | The failure it prevents |
|---|---|---|
| **Bronze** | Append-only, immutable | Losing the ability to reproduce any downstream number from the original bytes |
| **Silver** | Deterministic | Two runs disagreeing, which makes every KPI unfalsifiable |
| **Gold** | Idempotent | A rerun double-counting trips (BDD-04) |

## Check before you commit

```bash
python3 .claude/skills/medallion-transform/scripts/check_layer_contracts.py
python3 .claude/skills/medallion-transform/scripts/check_layer_contracts.py --staged
```

Catches non-deterministic constructs in Silver, mutations against Bronze, `INSERT INTO` a Gold
mart, and coordinate-derived measures described as road distance. It runs in `.githooks/pre-commit`
when `src/` or `configs/` files are staged.

It is a linter, so it catches shapes, not intent. It cannot tell you that a join silently dropped
rows. The reasoning below is the part that matters.

## Bronze — append-only

Every row carries `source_file`, `source_hash` and `ingested_at`. Never `UPDATE`, `DELETE`,
`MERGE` or `TRUNCATE` a landed row.

**A correction is a new ingestion, not an edit.** If the source file was wrong, land the corrected
file as a new batch with its own hash and let Silver resolve which wins. Editing Bronze destroys
the audit trail that makes every downstream number defensible — and it is irreversible in a way
that is invisible afterwards.

Re-running ingestion with the same `source_hash` must add zero rows (BDD-01). That is what makes
the job safe to retry.

## Silver — deterministic

Same Bronze rows in, byte-identical Silver rows out. Concretely, none of these belong in a Silver
transformation:

- `current_timestamp()`, `current_date`, `now()` — use `ingested_at` from Bronze instead
- `rand()`, `random()`, `uuid()`, `monotonically_increasing_id()`
- `LIMIT` without `ORDER BY`, or `TABLESAMPLE`
- any lookup against a table that changes independently

Determinism is what lets you re-derive Silver from Bronze and get the same answer, which is what
makes a KPI checkable at all. Without it "the number changed" has no diagnosis.

Silver is also where the derived fields (spec §5) and the DQ rules land: `estimated_distance_km`,
`estimated_speed_kmh`, `route_key`, `is_valid_trip`, the outlier flags. Rejections go to
`silver_trips_quarantine`; flags stay on the row. See the `dq-rule-authoring` skill.

## Gold — idempotent

A rerun replaces a partition wholesale. Never `INSERT INTO` a Gold mart — use a replace-where or a
merge keyed on the mart's grain.

The test is BDD-04: run the Gold job twice over unchanged Silver and get identical KPI values. If
the second run changes anything, the mart is appending.

Five marts, and there is no `gold_ml_metrics` — model metrics are out of scope. Which KPI lives where is
in `configs/kpi_config.yml`; read it rather than reproducing a formula from memory, because a
formula duplicated into SQL is a formula that will drift.

## Naming and wording

- `bronze_trips` · `silver_trips`, `silver_trips_quarantine` · `gold_<domain>_*`
- Any coordinate-derived measure is prefixed **`estimated_`** — no exceptions
- Durations: store seconds, present minutes, never mix within a column
- Each KPI model carries its `KPI-0NN` id in its description so lineage stays greppable

**The wording rule (BDD-07).** `estimated_distance_km` is straight-line Haversine distance. Real
taxi routes are longer, by a factor that varies with the route — so the error is not a constant you
can correct for, and `estimated_speed_kmh` systematically understates real driving speed. Never
label either as actual, road, driving or route distance/speed, in a column alias, a description, a
dashboard title or a docstring. The linter checks this; the reason it matters is that a
mislabelled column gets used for decisions the number cannot support.

## Where does this logic belong?

| The logic… | Belongs in |
|---|---|
| reads the source file, records provenance | Bronze |
| types, dedupes, derives, validates a **row** | Silver |
| aggregates across rows into a **metric** | Gold |
| needs an approved threshold | Blocked — see `threshold-decision` |
| changes what a KPI means | Blocked — see `kpi-contract-guard` |

When a rule could sit in two layers, prefer the earlier one: a derivation computed once in Silver
is consistent everywhere downstream, while the same derivation repeated in three Gold marts will
eventually disagree with itself.
