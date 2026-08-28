"""Generate the executive dashboard .lvdash.json from the repo's own queries.

Panels and labels follow docs/dashboards/executive-dashboard.md. The three labelling rules in
that guide are not stylistic and are applied here: 'estimated' never 'actual/road/driving'
(BDD-07), no 'congestion' wording, and vendor percentiles shown beside the mean.

Two Lakeview details this file exists to get right:

* A widget's visible title is spec.frame.title with showTitle. encodings.*.displayName only
  names the field inside the widget, so a counter with a displayName and no frame renders as
  a bare number with no label.
* A table column needs the full column object - type, displayAs, visible, order and title -
  not just fieldName. A partial column object renders as
  "Visualization has no fields selected."
"""
import json
import pathlib

Q = pathlib.Path("src/dashboards/queries")


def sql(name):
    """The repo query, comments stripped, as the dashboard's copy of it."""
    text = Q.joinpath(name).read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    return body.strip().rstrip(";")


def dataset(name, display, query):
    return {"name": name, "displayName": display, "queryLines": query.splitlines(keepends=True)}


def q(ds, fields, disaggregated):
    return [{"name": "main_query",
             "query": {"datasetName": ds,
                       "fields": [{"name": n, "expression": e} for n, e in fields],
                       "disaggregated": disaggregated}}]


def frame(title, description=None):
    f = {"showTitle": True, "title": title}
    if description:
        f["showDescription"] = True
        f["description"] = description
    return f


def counter(wname, ds, field, title, description=None):
    return {"name": wname, "queries": q(ds, [(field, "`" + field + "`")], True),
            "spec": {"version": 2, "widgetType": "counter",
                     "encodings": {"value": {"fieldName": field, "displayName": title}},
                     "frame": frame(title, description)}}


def chart(wname, ds, kind, x, y, title, disaggregated=False, xtype="quantitative",
          description=None):
    return {"name": wname, "queries": q(ds, [x[:2], y[:2]], disaggregated),
            "spec": {"version": 3, "widgetType": kind,
                     "encodings": {
                         "x": {"fieldName": x[0], "scale": {"type": xtype},
                               "displayName": x[2]},
                         "y": {"fieldName": y[0], "scale": {"type": "quantitative"},
                               "displayName": y[2]}},
                     "frame": frame(title, description)}}


def col(field, title, ctype, order):
    """A full Lakeview table column. Every key here is present in dashboards Databricks
    itself writes; a subset does not render."""
    numeric = ctype in ("integer", "float")
    display_as = "number" if numeric else ("boolean" if ctype == "boolean" else "string")
    return {"fieldName": field,
            "booleanValues": ["false", "true"],
            "imageUrlTemplate": "{{ @ }}",
            "imageTitleTemplate": "{{ @ }}",
            "imageWidth": "",
            "imageHeight": "",
            "linkUrlTemplate": "{{ @ }}",
            "linkTextTemplate": "{{ @ }}",
            "linkTitleTemplate": "{{ @ }}",
            "linkOpenInNewTab": True,
            "type": ctype,
            "displayAs": display_as,
            "visible": True,
            "order": order,
            "title": title,
            "allowSearch": False,
            "alignContent": "right" if numeric else "left",
            "allowHTML": False,
            "highlightLinks": False,
            "useMonospaceFont": False,
            "preserveWhitespace": False,
            "displayName": title}


def table(wname, ds, cols, title, description=None):
    """A table needs more than encodings.columns: without invisibleColumns, itemsPerPage,
    paginationSize, condensed and withRowNumber the widget is stored happily by the API and
    then renders as "Visualization has no fields selected"."""
    return {"name": wname,
            "queries": q(ds, [(c[0], "`" + c[0] + "`") for c in cols], True),
            "spec": {"version": 1, "widgetType": "table",
                     "encodings": {"columns": [col(f, t, ct, 100000 + i)
                                               for i, (f, t, ct) in enumerate(cols)]},
                     "invisibleColumns": [],
                     "allowHTMLByDefault": False,
                     "itemsPerPage": 25,
                     "paginationSize": "default",
                     "condensed": True,
                     "withRowNumber": False,
                     "frame": frame(title, description)}}


def text(wname, md):
    return {"name": wname, "textbox_spec": md}


def place(widget, x, y, w, h):
    return {"widget": widget, "position": {"x": x, "y": y, "width": w, "height": h}}


geo_inner = sql("03_top_areas_and_routes.sql")


def geo_slice(dim):
    return "SELECT * FROM (\n" + geo_inner + "\n) WHERE dimension = '" + dim + "'"


datasets = [
    dataset("exec_tiles", "Executive tiles (KPI-001..006, 009, 018)",
            sql("01_executive_tiles.sql")),
    dataset("demand", "Demand trend (KPI-007, KPI-008)", sql("02_demand_trend.sql")),
    dataset("geo_pickup", "Top pickup areas (KPI-010)", geo_slice("pickup_area")),
    dataset("geo_dropoff", "Top drop-off areas (KPI-011)", geo_slice("dropoff_area")),
    dataset("geo_route", "Top routes (KPI-012)", geo_slice("route")),
    dataset("vendor", "Vendor comparison (KPI-013..015)", sql("04_vendor_comparison.sql")),
    dataset("dq", "Data quality (KPI-018..020)", sql("05_data_quality.sql")),
    dataset("quarantine", "Quarantine breakdown (DQ-015)",
            sql("06_quarantine_breakdown.sql")),
]

TITLE = (
    "# NYC Taxi Operations\n\n"
    "Built from the Gold marts. Distance and speed are **estimated** — geodesic "
    "straight-line, never road distance (BDD-07). KPI-016 and KPI-017 have no tiles because "
    "All 20 KPIs are live: the six thresholds were approved on 2026-08-29 from profiling evidence (contract v2.0)."
)

GEODESIC = "Geodesic straight-line, not road distance."

layout = [
    place(text("w_title", TITLE), 0, 0, 6, 2),

    # Tile row 1 — KPI-001, 002, 003
    place(counter("w_trips", "exec_tiles", "kpi_001_total_trips",
                  "Total Trips", "KPI-001"), 0, 2, 2, 3),
    place(counter("w_avg_dur", "exec_tiles", "kpi_002_avg_duration_min",
                  "Avg Trip Duration (min)", "KPI-002"), 2, 2, 2, 3),
    place(counter("w_med_dur", "exec_tiles", "kpi_003_median_duration_min",
                  "Median Trip Duration (min)", "KPI-003"), 4, 2, 2, 3),

    # Tile row 2 — KPI-004, 005, 006
    place(counter("w_p90_dur", "exec_tiles", "kpi_004_p90_duration_min",
                  "P90 Trip Duration (min)", "KPI-004"), 0, 5, 2, 3),
    place(counter("w_est_dist", "exec_tiles", "kpi_005_avg_estimated_distance_km",
                  "Avg Estimated Distance (km)", "KPI-005 · " + GEODESIC), 2, 5, 2, 3),
    place(counter("w_est_speed", "exec_tiles", "kpi_006_avg_estimated_speed_kmh",
                  "Avg Estimated Speed (km/h)", "KPI-006 · " + GEODESIC), 4, 5, 2, 3),

    # Tile row 3 - the two KPIs released by the 2026-08-29 threshold approvals
    place(counter("w_long_trip", "exec_tiles", "kpi_016_long_trip_rate_pct",
                  "Long Trip Rate (%)",
                  "KPI-016 · trips over 3,600s (60 min), approved 2026-08-29"), 0, 8, 2, 3),
    place(counter("w_low_speed", "exec_tiles", "kpi_017_low_speed_rate_pct",
                  "Low-Speed Trip Rate (%)",
                  "KPI-017 · under 5 km/h. An anomaly-candidate rate, NOT a congestion "
                  "rate - the speed is geodesic and cannot distinguish the cause."), 2, 8, 2, 3),
    place(counter("w_peak", "exec_tiles", "kpi_009_peak_hour",
                  "Peak Hour", "KPI-009 · hour of day with the most trips"), 4, 8, 2, 3),

    # Tile row 4 - data quality, and the quarantine that DQ-009/010 now produces
    place(counter("w_dq", "exec_tiles", "kpi_018_data_quality_pct",
                  "Data Quality Score (%)", "KPI-018 · valid ÷ total across all batches"),
          0, 11, 2, 3),
    place(counter("w_quarantined", "dq", "quarantined_records",
                  "Quarantined Records",
                  "Rejected to silver_trips_quarantine, never deleted. total = valid + "
                  "quarantined still holds."), 2, 11, 2, 3),
    place(table("w_quarantine", "quarantine",
                [("rule_id", "Rule", "string"),
                 ("quarantine_reason", "Reason", "string"),
                 ("rejected_rows", "Rejected rows", "integer"),
                 ("pct_of_batch", "% of batch", "float")],
                "Quarantine by Rule",
                "Every rejected row appears here under the rule that rejected it."),
          4, 11, 2, 3),

    # Demand
    place(chart("w_daily", "demand", "line",
                ("pickup_date", "`pickup_date`", "Date"),
                ("daily_trips", "MAX(`trips_per_day`)", "Trips per day"),
                "Daily Demand Trend", xtype="temporal", description="KPI-007"), 0, 14, 6, 6),
    place(chart("w_hourly", "demand", "bar",
                ("pickup_hour", "`pickup_hour`", "Hour of day"),
                ("hourly_trips", "SUM(`trips_per_hour`)", "Trips"),
                "Trips by Hour of Day", description="KPI-008"), 0, 20, 3, 6),
    place(chart("w_vendor_share", "vendor", "bar",
                ("vendor_id", "`vendor_id`", "Vendor"),
                ("trip_share_pct", "`trip_share_pct`", "Trip share (%)"),
                "Vendor Trip Share", disaggregated=True, description="KPI-013"), 3, 20, 3, 6),

    # Vendor detail — percentiles beside the mean, never the mean alone.
    place(table("w_vendor", "vendor",
                [("vendor_id", "Vendor", "integer"),
                 ("vendor_trips", "Trips", "integer"),
                 ("trip_share_pct", "Share (%)", "float"),
                 ("avg_duration_min", "Avg (min)", "float"),
                 ("median_duration_min", "P50 (min)", "float"),
                 ("p90_duration_min", "P90 (min)", "float"),
                 ("avg_estimated_distance_km", "Avg Est. Distance (km)", "float"),
                 ("avg_estimated_speed_kmh", "Avg Est. Speed (km/h)", "float")],
                "Vendor Comparison (KPI-013..015)",
                "P50 and P90 sit beside the mean on purpose: durations are right-skewed and "
                "vendor trip mixes differ, so averages alone invite a conclusion the data does "
                "not support."), 0, 26, 6, 4),

    # Geography. Areas are counts only — KPI-010/011 are COUNT(DISTINCT id), so the mart
    # carries NULL for their duration and distance columns by design. Routes carry the
    # companion metrics the contract defines for them, so they get a table.
    place(chart("w_pickup", "geo_pickup", "bar",
                ("area_key", "`area_key`", "Pickup area"),
                ("trip_count", "`trip_count`", "Trips"),
                "Top 10 Pickup Areas", disaggregated=True, xtype="categorical",
                description="KPI-010 · trip count only, by contract"), 0, 30, 3, 6),
    place(chart("w_dropoff", "geo_dropoff", "bar",
                ("area_key", "`area_key`", "Drop-off area"),
                ("trip_count", "`trip_count`", "Trips"),
                "Top 10 Drop-off Areas", disaggregated=True, xtype="categorical",
                description="KPI-011 · trip count only, by contract"), 3, 30, 3, 6),
    place(table("w_routes", "geo_route",
                [("area_key", "Route", "string"),
                 ("trip_count", "Trips", "integer"),
                 ("avg_duration_min", "Avg (min)", "float"),
                 ("median_duration_min", "P50 (min)", "float"),
                 ("p90_duration_min", "P90 (min)", "float"),
                 ("avg_estimated_distance_km", "Avg Est. Distance (km)", "float"),
                 ("avg_estimated_speed_kmh", "Avg Est. Speed (km/h)", "float")],
                "Top 10 Routes (KPI-012)",
                "Routes carry companion metrics; pickup and drop-off areas do not."),
          0, 36, 6, 4),

    # Data-quality components, shown separately rather than blended into one number.
    place(table("w_dq_detail", "dq",
                [("source_file", "Source", "string"),
                 ("total_records", "Total", "integer"),
                 ("valid_records", "Valid", "integer"),
                 ("quarantined_records", "Quarantined", "integer"),
                 ("kpi_018_quality_score_pct", "Quality (%)", "float"),
                 ("kpi_019_invalid_rate_pct", "Invalid (%)", "float"),
                 ("kpi_020_duplicate_rate_pct", "Duplicate (%)", "float"),
                 ("completeness_pct", "Completeness", "float"),
                 ("uniqueness_pct", "Uniqueness", "float"),
                 ("validity_pct", "Validity", "float"),
                 ("consistency_pct", "Consistency", "float"),
                 ("geographic_validity_pct", "Geo validity", "float"),
                 ("reconciles", "Reconciles", "boolean")],
                "Data Quality by Batch (KPI-018..020)",
                "Component scores are shown separately, not blended: a single number hides "
                "which dimension is failing. `reconciles` false means rows are disappearing."),
          0, 40, 6, 4),
]

dash = {"datasets": datasets,
        "pages": [{"name": "operations", "displayName": "NYC Taxi Operations",
                   "layout": layout}]}

out = pathlib.Path("src/dashboards/nyc_taxi_executive.lvdash.json")
out.write_bytes((json.dumps(dash, indent=2) + "\n").encode("utf-8"))
print("wrote " + str(out) + "  (" + format(out.stat().st_size, ",") + " bytes)")

defined = {ds["name"] for ds in datasets}
referenced = {w["widget"]["queries"][0]["query"]["datasetName"]
              for w in layout if w["widget"].get("queries")}
dangling = referenced - defined
unused = defined - referenced
assert not dangling, f"widgets reference undefined datasets: {sorted(dangling)}"
assert not unused, f"datasets defined but referenced by no widget: {sorted(unused)}"

titled = sum(1 for w in layout if w["widget"].get("spec", {}).get("frame", {}).get("showTitle"))
tables = [w for w in layout if w["widget"].get("spec", {}).get("widgetType") == "table"]
required = {"fieldName", "type", "displayAs", "visible", "order", "title", "displayName"}
bad = [w["widget"]["name"] for w in tables
       for c in w["widget"]["spec"]["encodings"]["columns"] if not required <= set(c)]
print("  widgets: " + str(len(layout)) + "   titled: " + str(titled)
      + "   tables: " + str(len(tables)) + "   incomplete columns: " + str(len(bad)))
