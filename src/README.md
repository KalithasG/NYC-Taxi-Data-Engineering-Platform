# src/

Pipeline code by stage. Built and verified locally against a synthetic fixture; see
`docs/architecture/databricks-setup.md` to run it on a workspace.

| Directory | Responsibility | Status |
|---|---|---|
| `ingestion/` | Acquire the source file, hash it, land Bronze immutably | **built, verified** |
| `profiling/` | The 16 profiling steps; emit `profile_*` tables and the report | **built, verified** — the *run* needs the dataset |
| `transformations/` | Bronze→Silver→Gold dbt models | **built, verified** — 18 of 20 KPIs |
| `dashboards/` | Six panel queries over the Gold marts | **built, all execute** |
| `orchestration/` | Lakeflow job definition + Databricks preflight check | **built** |
| `quality/` | DQ rule execution lives in the dbt Silver models | folded into `transformations/` |
| `features/` | Reserved — future enrichment; nothing in scope today | — |

Before writing anything here, read `AGENTS.md` — particularly the layer contracts (Bronze
immutable, Silver deterministic, Gold idempotent) and the five rules.

`features/` is reserved for future enrichment (taxi-zone polygons, weather, events — the
extensions listed in KPI contract §19). Nothing belongs there today, and model feature
engineering is out of scope for this platform entirely.
