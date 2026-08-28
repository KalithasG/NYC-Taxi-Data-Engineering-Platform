# Executive Dashboard — Build Guide

Layout from `docs/business/kpi-discussion.md` §11. Six panels over the Gold marts, one query
each in `src/dashboards/queries/`. Every query has been executed against the built marts — none
of this is untested SQL.

## Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                      NYC TAXI OPERATIONS                            │
├────────────┬────────────┬────────────┬──────────────────────────────┤
│ Total      │ Avg Trip   │ Median     │ P90 Trip                     │
│ Trips      │ Duration   │ Duration   │ Duration                     │
├────────────┼────────────┼────────────┼──────────────────────────────┤
│ Avg Est.   │ Avg Est.   │ Peak Hour  │ Data Quality                 │
│ Distance   │ Speed      │            │ Score                        │
├────────────┴────────────┴────────────┴──────────────────────────────┤
│              Daily / hourly demand trend  (KPI-007, KPI-008)        │
├───────────────────────────────┬─────────────────────────────────────┤
│ Top pickup areas / routes     │ Vendor comparison                   │
│ (KPI-010, 011, 012)           │ (KPI-013, 014, 015)                 │
├───────────────────────────────┴─────────────────────────────────────┤
│    Data quality + quarantine breakdown  (KPI-018, 019, 020)         │
└─────────────────────────────────────────────────────────────────────┘
```

## Panels

| # | Panel | Query | KPIs | Visual |
|---|---|---|---|---|
| 1 | Executive tiles | `01_executive_tiles.sql` | 001–006, 009, 018 | Counter tiles |
| 2 | Demand trend | `02_demand_trend.sql` | 007, 008 | Line (daily) + bar (hour-of-day) |
| 3 | Top areas & routes | `03_top_areas_and_routes.sql` | 010, 011, 012 | Horizontal bar, filtered by `dimension` |
| 4 | Vendor comparison | `04_vendor_comparison.sql` | 013, 014, 015 | Grouped bar — **plot the percentiles, not just the mean** |
| 5 | Data quality | `05_data_quality.sql` | 018, 019, 020 | Tiles + component-score bar |
| 6 | Quarantine breakdown | `06_quarantine_breakdown.sql` | — | Bar by rule id |

## Building it in Databricks AI/BI

1. **SQL editor → paste a query → Save** as `nyc_taxi_<panel>`.
2. **Dashboards → Create dashboard →** add a visualisation per saved query.
3. Add a **date range filter** on `pickup_date` and wire it to panels 2 and 3.
4. Set the refresh schedule to match the pipeline job, not faster — a dashboard that refreshes
   more often than the data changes just costs serverless budget.

## Three labelling rules that are not stylistic

**KPI-005 and KPI-006 are geodesic.** Tile labels must read "Avg Estimated Distance" and
"Avg Estimated Speed" — never "actual", "road", "route" or "driving". Straight-line distance
understates a real taxi route by a factor that varies with the route, so it is not a constant
you can correct for or a caveat you can drop for brevity. This is BDD-07, and
`check_layer_contracts.py` enforces it on the models; on the dashboard it is on you.

**KPI-017, when it exists, is not a congestion rate.** Label it "Low-Speed Trip Rate", not
"Congestion". A low estimated speed has at least six candidate causes (profiling §22) and the
metric cannot distinguish them.

**Vendor panels need the percentiles visible.** A grouped bar of average duration by vendor
invites "vendor 1 is slower", which the data does not support — the distributions are skewed
and the trip mixes differ. Show P50/P90 alongside, or the panel is misleading by construction.

## What is not on the dashboard yet

**KPI-016 Long Trip Rate** and **KPI-017 Low-Speed Trip Rate** have no tiles, because their
thresholds are unapproved. `gold.trip_performance` carries
`kpi_016_withheld_pending_long_trip_seconds` instead of a value, so a panel built on it would
render an empty column rather than a wrong number.

Add both tiles once the thresholds are approved and the marts rebuild without
`--allow-withheld`. Until then their absence is the honest state, and a placeholder showing 0%
would be worse than nothing.

## Verifying a panel

Run its query against the marts before wiring it up:

```bash
python -m src.transformations.run --target local --allow-withheld
# then execute any file in src/dashboards/queries/ against nyc_taxi_dev
```

Panel 1 should agree with panel 5 on total trips, and panel 2's summed `trips_per_hour` should
equal panel 1's `kpi_001_total_trips`. If they disagree, the marts are inconsistent — that is a
pipeline bug, not a dashboard bug.
