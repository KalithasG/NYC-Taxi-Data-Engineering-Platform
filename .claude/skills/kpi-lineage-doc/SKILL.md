---
name: kpi-lineage-doc
description: "Documents and verifies the lineage of every KPI — source column through Silver derivation and transformation to Gold metric and consumer — as required by KPI contract §17. Use this whenever asked where a number comes from, what feeds a metric, what a column or dashboard figure depends on, what breaks if a source column changes, or to trace, map, document or audit data lineage. Also use when adding a KPI to a mart, when doing impact analysis before changing a source column or derivation, and when docs/architecture/kpi-lineage.md needs regenerating after configs/kpi_config.yml changes."
---

# KPI Lineage Documentation

KPI contract §17 requires a traceable chain per Gold KPI:

```text
Source Column -> Silver Derived Column -> Transformation -> Gold Metric -> Consumer
```

The purpose is an answerable question. "Where does this number come from?" should be answered by a
document in seconds, not by an afternoon of reading SQL. A KPI whose lineage nobody can state is a
KPI nobody can defend when it is challenged — and metrics get challenged exactly when they matter.

## Check and generate

```bash
python3 .claude/skills/kpi-lineage-doc/scripts/check_lineage.py           # coverage report
python3 .claude/skills/kpi-lineage-doc/scripts/check_lineage.py --strict  # fail on gaps
python3 .claude/skills/kpi-lineage-doc/scripts/check_lineage.py --scaffold
python3 .claude/skills/kpi-lineage-doc/scripts/check_lineage.py --kpi KPI-005
```

`--scaffold` derives blocks from `configs/kpi_config.yml` for every KPI missing one. `--strict`
fails when a block is absent, missing a stage, or still carrying an unfilled `<placeholder>` — a
template with the right headings is not documented lineage.

`docs/architecture/kpi-lineage.md` currently holds all 20 blocks. Regenerate it whenever the KPI
config changes; a stale lineage document is worse than none, because it is believed.

## What the generator can and cannot know

Derived from the config and reliable: the source columns, the Silver derivation, the
transformation, the mart, the grain and the filter.

**Provisional:** the consumer. No dashboard exists yet, so those entries state intent. Correct them
against reality once the AI/BI dashboard is built — that is the one column a human has to own.

## Reading a chain

```text
pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude
        |
        v   Haversine transformation (Earth radius 6371 km)
estimated_distance_km
        |
        v   AVG(estimated_distance_km)
KPI-005 Average Estimated Distance   ->   gold.trip_performance
        |
        v
Operations dashboard
```

Read it in both directions. Downward answers "what does this produce?"; upward answers "what
breaks if I change this?" The second is the one that saves you — before altering a source column,
a derivation or a DQ rule, read up every chain it appears in.

## Three things worth carrying into a chain

**Caveats travel with the number.** KPI-005 and KPI-006 are geodesic, not road measures. That
caveat belongs in the lineage block because the lineage is where someone looks when they are about
to use the metric for something. The generator copies it from the config automatically.

**Blocked thresholds are lineage.** KPI-016 and KPI-017 depend on values that do not exist yet.
The block records the dependency and its status, so "why is this KPI missing?" has an answer.

**Audit lineage is real lineage.** KPI-018/019/020 do not trace back through a trip column — they
trace through the quarantine and duplicate audit tables. KPI-020 in particular reads the
*pre-deduplication* count, and recording that in the chain is what stops someone later "fixing" it
to read the deduplicated table, where it would report zero forever.

## When a chain cannot be completed

Say so in the block rather than inventing a plausible link. An honest gap is a work item; a
fabricated chain is a document that lies confidently, which is the failure mode this whole file
exists to prevent.
