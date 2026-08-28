#!/usr/bin/env python3
"""
generate_dashboard_snapshot.py — render a shareable static snapshot of the Gold marts.

The AI/BI dashboard itself cannot be shared publicly: Databricks requires every viewer to be
registered with the account, so its URL is a login wall for anyone outside the workspace. This
reads the same Gold marts the dashboard reads and emits one self-contained HTML file that opens
anywhere — the version a reader without Databricks access can actually see.

It is a snapshot, not a live view. The provenance strip carries the run id, source hash and row
counts so a reader can tell exactly which pipeline run produced the numbers.

    python scripts/generate_dashboard_snapshot.py                 # query Databricks, then render
    python scripts/generate_dashboard_snapshot.py --from cache.json  # render from a saved pull

Reads DATABRICKS_HOST / DATABRICKS_HTTP_PATH / DATABRICKS_TOKEN from .env (gitignored).
"""

import argparse
import datetime
import decimal
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "dashboards" / "snapshot.html"

QUERIES = {
    "tiles": """
        SELECT (SELECT SUM(kpi_001_total_trips) FROM gold.trip_performance) AS total_trips,
          (SELECT ROUND(AVG(trip_duration)/60.0,1) FROM silver_trips) AS avg_min,
          (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY trip_duration)/60.0,1)
             FROM silver_trips) AS med_min,
          (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY trip_duration)/60.0,1)
             FROM silver_trips) AS p90_min,
          (SELECT ROUND(AVG(estimated_distance_km),2) FROM silver_trips) AS avg_km,
          (SELECT ROUND(AVG(estimated_speed_kmh),1) FROM silver_trips) AS avg_kmh,
          (SELECT ROUND(SUM(kpi_016_long_trip_rate_pct*kpi_001_total_trips)
                        /SUM(kpi_001_total_trips),2) FROM gold.trip_performance) AS kpi016,
          (SELECT ROUND(SUM(kpi_017_low_speed_rate_pct*kpi_001_total_trips)
                        /SUM(kpi_001_total_trips),2) FROM gold.trip_performance) AS kpi017,
          (SELECT kpi_009_peak_hour FROM gold.demand_metrics
            ORDER BY kpi_009_peak_hour_trip_count DESC, pickup_date LIMIT 1) AS peak_hour,
          (SELECT ROUND(100.0*SUM(valid_records)/SUM(total_records),2)
             FROM gold.data_quality) AS dq_pct,
          (SELECT SUM(quarantined_records) FROM gold.data_quality) AS quarantined,
          (SELECT SUM(total_records) FROM gold.data_quality) AS total_records""",
    "run": "SELECT profiling_run_id, source_file, source_hash, row_count FROM profiling.profile_run "
           "ORDER BY profiling_run_id DESC LIMIT 1",
    "daily": "SELECT pickup_date, MAX(kpi_007_trips_per_day) AS trips FROM gold.demand_metrics "
             "GROUP BY pickup_date ORDER BY pickup_date",
    "hourly": "SELECT pickup_hour, SUM(kpi_008_trips_per_hour) AS trips FROM gold.demand_metrics "
              "GROUP BY pickup_hour ORDER BY pickup_hour",
    "vendor": """
        SELECT vendor_id, vendor_trips, ROUND(kpi_013_vendor_trip_share_pct,2) AS share,
          ROUND(kpi_014_avg_duration_seconds/60.0,1) AS avg_min,
          ROUND(median_duration_seconds/60.0,1) AS p50_min,
          ROUND(kpi_015_p90_duration_seconds/60.0,1) AS p90_min,
          ROUND(avg_estimated_distance_km,2) AS km, ROUND(avg_estimated_speed_kmh,1) AS kmh
        FROM gold.vendor_performance ORDER BY vendor_id""",
    "pickup": "SELECT area_key, trip_count FROM gold.geographic_metrics "
              "WHERE dimension='pickup_area' AND rank_in_dimension<=10 ORDER BY rank_in_dimension",
    "dropoff": "SELECT area_key, trip_count FROM gold.geographic_metrics "
               "WHERE dimension='dropoff_area' AND rank_in_dimension<=10 ORDER BY rank_in_dimension",
    "routes": """
        SELECT area_key, trip_count, ROUND(avg_duration_seconds/60.0,1) AS avg_min,
          ROUND(median_duration_seconds/60.0,1) AS p50_min,
          ROUND(p90_duration_seconds/60.0,1) AS p90_min,
          ROUND(avg_estimated_distance_km,2) AS km, ROUND(avg_estimated_speed_kmh,1) AS kmh
        FROM gold.geographic_metrics WHERE dimension='route' AND rank_in_dimension<=10
        ORDER BY rank_in_dimension""",
    "quarantine": "SELECT rule_id, quarantine_reason, COUNT(*) AS rejected "
                  "FROM silver_trips_quarantine GROUP BY rule_id, quarantine_reason "
                  "ORDER BY rejected DESC",
    "dq": """
        SELECT total_records, valid_records, quarantined_records,
          ROUND(kpi_018_data_quality_score_pct,3) AS quality,
          ROUND(kpi_019_invalid_record_rate_pct,3) AS invalid,
          ROUND(kpi_020_duplicate_rate_pct,3) AS dup,
          ROUND(completeness_score_pct,3) AS completeness,
          ROUND(uniqueness_score_pct,3) AS uniqueness,
          ROUND(validity_score_pct,3) AS validity,
          ROUND(consistency_score_pct,3) AS consistency,
          ROUND(geographic_validity_score_pct,3) AS geo, reconciles
        FROM gold.data_quality""",
}


def _scalar(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10]
    return v


def pull():
    from dotenv import dotenv_values
    from databricks import sql
    env = dotenv_values(ROOT / ".env")
    host = env["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    data = {}
    with sql.connect(server_hostname=host, http_path=env["DATABRICKS_HTTP_PATH"],
                     access_token=env["DATABRICKS_TOKEN"]) as c, c.cursor() as cur:
        cur.execute("USE CATALOG nyc_taxi_dev")
        cur.execute("USE SCHEMA silver")
        for name, q in QUERIES.items():
            cur.execute(q)
            cols = [d[0] for d in cur.description]
            data[name] = [{k: _scalar(v) for k, v in zip(cols, row)} for row in cur.fetchall()]
            print(f"  {name:11s} {len(data[name])} row(s)")
    return data


# ---------------------------------------------------------------- svg helpers

def area_chart(rows, xkey, ykey, w=1040, h=190, pad=26):
    """Daily trend. Area fill under a line, faint gridlines, emphasized final point."""
    ys = [r[ykey] for r in rows]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1
    n = len(rows)

    def px(i):
        return pad + i * (w - 2 * pad) / max(n - 1, 1)

    def py(v):
        return h - pad - (v - lo) / span * (h - 2 * pad)

    line = " ".join(f"{'M' if i == 0 else 'L'}{px(i):.1f},{py(v):.1f}"
                    for i, v in enumerate(ys))
    fill = f"{line} L{px(n-1):.1f},{h-pad:.1f} L{px(0):.1f},{h-pad:.1f} Z"
    grid = "".join(
        f'<line class="grid" x1="{pad}" y1="{py(lo + span*f):.1f}" '
        f'x2="{w-pad}" y2="{py(lo + span*f):.1f}"/>' for f in (0, 0.5, 1))
    labels = (f'<text class="ax" x="{pad}" y="{h-6}">{rows[0][xkey]}</text>'
              f'<text class="ax" x="{w-pad}" y="{h-6}" text-anchor="end">{rows[-1][xkey]}</text>'
              f'<text class="ax" x="{pad}" y="{py(hi)-7:.1f}">{hi:,} peak</text>')
    dot = f'<circle class="dot" cx="{px(n-1):.1f}" cy="{py(ys[-1]):.1f}" r="3.5"/>'
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Daily trips, '
            f'{rows[0][xkey]} to {rows[-1][xkey]}">{grid}'
            f'<path class="area" d="{fill}"/><path class="line" d="{line}"/>{dot}{labels}</svg>')


def bar_chart(rows, xkey, ykey, w=520, h=190, pad=26):
    """Hour-of-day profile."""
    ys = [r[ykey] for r in rows]
    hi = max(ys) or 1
    n = len(rows)
    bw = (w - 2 * pad) / n
    bars = ""
    for i, r in enumerate(rows):
        bh = (r[ykey] / hi) * (h - 2 * pad)
        x = pad + i * bw
        peak = ' peak' if r[ykey] == hi else ''
        bars += (f'<rect class="bar{peak}" x="{x+1.2:.1f}" y="{h-pad-bh:.1f}" '
                 f'width="{bw-2.4:.1f}" height="{bh:.1f}"><title>{r[xkey]}:00 — '
                 f'{r[ykey]:,} trips</title></rect>')
    ticks = "".join(f'<text class="ax" x="{pad + (i+0.5)*bw:.1f}" y="{h-6}" '
                    f'text-anchor="middle">{rows[i][xkey]}</text>'
                    for i in range(0, n, 4))
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Trips by hour of day">'
            f'{bars}{ticks}</svg>')


def hbars(rows, label_key, value_key):
    hi = max(r[value_key] for r in rows) or 1
    out = ""
    for r in rows:
        pct = r[value_key] / hi * 100
        out += (f'<div class="hb"><span class="hb-l">{r[label_key]}</span>'
                f'<span class="hb-t"><span class="hb-f" style="width:{pct:.1f}%"></span></span>'
                f'<span class="hb-v">{r[value_key]:,}</span></div>')
    return out


def meter(label, pct):
    state = "ok" if pct >= 99.99 else ("warn" if pct >= 99 else "crit")
    return (f'<div class="meter"><span class="m-l">{label}</span>'
            f'<span class="m-t"><span class="m-f {state}" style="width:{pct:.3f}%"></span></span>'
            f'<span class="m-v">{pct:.3f}%</span></div>')


# ---------------------------------------------------------------- page

def render(d):
    t = d["tiles"][0]
    dq = d["dq"][0]
    run = d["run"][0] if d.get("run") else {}
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tiles = [
        ("KPI-001", "Total Trips", f"{t['total_trips']:,}", "valid population", ""),
        ("KPI-002", "Avg Trip Duration", f"{t['avg_min']}", "minutes", ""),
        ("KPI-003", "Median Trip Duration", f"{t['med_min']}", "minutes", ""),
        ("KPI-004", "P90 Trip Duration", f"{t['p90_min']}", "minutes", ""),
        ("KPI-005", "Avg Estimated Distance", f"{t['avg_km']}", "km · geodesic", "est"),
        ("KPI-006", "Avg Estimated Speed", f"{t['avg_kmh']}", "km/h · geodesic", "est"),
        ("KPI-016", "Long Trip Rate", f"{t['kpi016']}%", "over 60 min", "new"),
        ("KPI-017", "Low-Speed Trip Rate", f"{t['kpi017']}%", "under 5 km/h", "new"),
        ("KPI-009", "Peak Hour", f"{t['peak_hour']}:00", "most trips in a day", ""),
        ("KPI-018", "Data Quality Score", f"{t['dq_pct']}%", "valid ÷ total", ""),
        ("DQ-015", "Quarantined", f"{t['quarantined']:,}", "rejected, retained", "quar"),
    ]
    tile_html = ""
    for kid, name, val, sub, mark in tiles:
        badge = {"est": '<span class="chip est">estimated</span>',
                 "new": '<span class="chip new">threshold approved</span>',
                 "quar": '<span class="chip quar">auditable</span>'}.get(mark, "")
        tile_html += (f'<article class="tile"><header><span class="kid">{kid}</span>{badge}</header>'
                      f'<p class="tv">{val}</p><h3>{name}</h3><p class="ts">{sub}</p></article>')

    vendor_rows = "".join(
        f'<tr><td class="mono">Vendor {v["vendor_id"]}</td><td>{v["vendor_trips"]:,}</td>'
        f'<td>{v["share"]}%</td><td>{v["avg_min"]}</td><td>{v["p50_min"]}</td>'
        f'<td>{v["p90_min"]}</td><td>{v["km"]}</td><td>{v["kmh"]}</td></tr>' for v in d["vendor"])

    route_rows = "".join(
        f'<tr><td class="mono">{r["area_key"]}</td><td>{r["trip_count"]:,}</td>'
        f'<td>{r["avg_min"]}</td><td>{r["p50_min"]}</td><td>{r["p90_min"]}</td>'
        f'<td>{r["km"]}</td><td>{r["kmh"]}</td></tr>' for r in d["routes"])

    quar_rows = "".join(
        f'<tr><td class="mono">{q["rule_id"]}</td><td class="mono sm">{q["quarantine_reason"]}</td>'
        f'<td>{q["rejected"]:,}</td>'
        f'<td>{100.0*q["rejected"]/dq["total_records"]:.4f}%</td></tr>'
        for q in d["quarantine"])

    meters = "".join(meter(lbl, dq[k]) for lbl, k in (
        ("Completeness", "completeness"), ("Uniqueness", "uniqueness"), ("Validity", "validity"),
        ("Consistency", "consistency"), ("Geographic validity", "geo")))

    return TEMPLATE.format(
        generated=generated,
        run_id=run.get("profiling_run_id", "—"),
        source_file=run.get("source_file", "train.csv"),
        source_hash=(run.get("source_hash") or "")[:16],
        total=f"{dq['total_records']:,}", valid=f"{dq['valid_records']:,}",
        quar=f"{dq['quarantined_records']:,}",
        tiles=tile_html,
        daily=area_chart(d["daily"], "pickup_date", "trips"),
        hourly=bar_chart(d["hourly"], "pickup_hour", "trips"),
        pickup=hbars(d["pickup"], "area_key", "trip_count"),
        dropoff=hbars(d["dropoff"], "area_key", "trip_count"),
        vendor_rows=vendor_rows, route_rows=route_rows, quar_rows=quar_rows, meters=meters,
        invalid=dq["invalid"], dup=dq["dup"],
    )


TEMPLATE = """<title>NYC Taxi Operations Snapshot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  --paper:#FAF8F4; --card:#FFFFFF; --sunk:#F1EDE6;
  --ink:#161C1F; --ink2:#3D4A4F; --ink3:#6B7A80;
  --rule:#DFD8CD; --accent:#B26A16; --chart:#2F6169;
  --ok:#2F7A4D; --warn:#9A7016; --crit:#A6392E;
  --shadow:0 1px 2px rgba(22,28,31,.06), 0 8px 24px -18px rgba(22,28,31,.5);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#101619; --card:#161E21; --sunk:#1C2529;
    --ink:#E9E5DE; --ink2:#B3BDC0; --ink3:#7E8C92;
    --rule:#263136; --accent:#E0A055; --chart:#5FA3AC;
    --ok:#5FBF87; --warn:#D7A93F; --crit:#E08472;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -20px rgba(0,0,0,.9);
  }}
}}
:root[data-theme="dark"] {{
  --paper:#101619; --card:#161E21; --sunk:#1C2529;
  --ink:#E9E5DE; --ink2:#B3BDC0; --ink3:#7E8C92;
  --rule:#263136; --accent:#E0A055; --chart:#5FA3AC;
  --ok:#5FBF87; --warn:#D7A93F; --crit:#E08472;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -20px rgba(0,0,0,.9);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Source Serif 4",Georgia,serif; font-size:16px; line-height:1.6;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1120px; margin:0 auto; padding:44px 24px 72px; }}
h1,h2,h3,.kid,.chip,.ax,th,.hb-l,.hb-v,.m-l,.m-v,.tv,.ts {{
  font-family:Archivo,"Helvetica Neue",Arial,sans-serif;
}}
h1 {{ font-size:clamp(30px,4.4vw,44px); line-height:1.05; margin:0 0 10px;
     letter-spacing:-.022em; font-weight:700; text-wrap:balance; }}
h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.14em; font-weight:600;
     color:var(--ink3); margin:0 0 16px; }}
h3 {{ font-size:14.5px; margin:2px 0 0; font-weight:600; letter-spacing:-.005em; }}
.lede {{ font-size:18px; color:var(--ink2); margin:0 0 22px; max-width:64ch; }}
.mono, .tv, td, .ax, .hb-v, .m-v {{ font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums; }}
section {{ margin-top:44px; }}
.note {{ font-size:14.5px; color:var(--ink3); max-width:70ch; margin:14px 0 0; }}

/* provenance */
.prov {{ display:flex; flex-wrap:wrap; gap:0 30px; padding:14px 18px; background:var(--sunk);
  border:1px solid var(--rule); border-radius:3px; font-family:"IBM Plex Mono",monospace;
  font-size:12.5px; color:var(--ink2); }}
.prov b {{ color:var(--ink3); font-weight:500; }}

/* reconciliation — the platform's central claim, so it gets the largest type on the page */
.recon {{ border-left:3px solid var(--accent); padding:18px 22px; background:var(--card);
  border-radius:0 3px 3px 0; box-shadow:var(--shadow); }}
.eq {{ font-family:"IBM Plex Mono",monospace; font-size:clamp(17px,2.5vw,26px);
  font-variant-numeric:tabular-nums; letter-spacing:-.02em; margin:0; }}
.eq .op {{ color:var(--ink3); }} .eq .v {{ color:var(--ok); }} .eq .q {{ color:var(--accent); }}

/* tiles */
.tiles {{ display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(212px,1fr)); }}
.tile {{ background:var(--card); border:1px solid var(--rule); border-radius:3px;
  padding:14px 16px 16px; box-shadow:var(--shadow); }}
.tile header {{ display:flex; justify-content:space-between; align-items:center; gap:8px;
  min-height:20px; }}
.kid {{ font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--ink3);
  letter-spacing:.04em; }}
.chip {{ font-size:9.5px; text-transform:uppercase; letter-spacing:.09em; padding:2px 6px;
  border-radius:2px; font-weight:600; }}
.chip.est {{ background:color-mix(in srgb,var(--chart) 15%,transparent); color:var(--chart); }}
.chip.new {{ background:color-mix(in srgb,var(--accent) 17%,transparent); color:var(--accent); }}
.chip.quar {{ background:color-mix(in srgb,var(--warn) 17%,transparent); color:var(--warn); }}
.tv {{ font-size:31px; line-height:1.1; margin:10px 0 0; font-weight:500;
  letter-spacing:-.03em; }}
.ts {{ font-size:11.5px; color:var(--ink3); margin:3px 0 0; letter-spacing:.01em; }}

/* charts */
.panel {{ background:var(--card); border:1px solid var(--rule); border-radius:3px; padding:18px;
  box-shadow:var(--shadow); }}
.two {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); }}
svg {{ display:block; width:100%; height:auto; }}
.area {{ fill:color-mix(in srgb,var(--chart) 16%,transparent); }}
.line {{ fill:none; stroke:var(--chart); stroke-width:1.6; }}
.dot {{ fill:var(--accent); }}
.grid {{ stroke:var(--rule); stroke-width:1; }}
.bar {{ fill:color-mix(in srgb,var(--chart) 58%,transparent); }}
.bar.peak {{ fill:var(--accent); }}
.ax {{ font-family:"IBM Plex Mono",monospace; font-size:10px; fill:var(--ink3); }}

/* horizontal bars */
.hb {{ display:grid; grid-template-columns:104px 1fr 62px; align-items:center; gap:10px;
  margin-bottom:7px; }}
.hb-l {{ font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--ink2); }}
.hb-t {{ height:9px; background:var(--sunk); border-radius:1px; overflow:hidden; }}
.hb-f {{ display:block; height:100%; background:var(--chart); }}
.hb-v {{ font-size:11.5px; text-align:right; color:var(--ink2); }}

/* meters */
.meter {{ display:grid; grid-template-columns:150px 1fr 74px; align-items:center; gap:12px;
  margin-bottom:9px; }}
.m-l {{ font-size:12.5px; color:var(--ink2); }}
.m-t {{ height:7px; background:var(--sunk); border-radius:1px; overflow:hidden; }}
.m-f {{ display:block; height:100%; }}
.m-f.ok {{ background:var(--ok); }} .m-f.warn {{ background:var(--warn); }}
.m-f.crit {{ background:var(--crit); }}
.m-v {{ font-size:12px; text-align:right; color:var(--ink2); }}

/* tables */
.scroll {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th {{ text-align:right; font-size:10.5px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--ink3); font-weight:600; padding:0 0 9px; border-bottom:1px solid var(--rule); }}
th:first-child, td:first-child {{ text-align:left; }}
td {{ text-align:right; padding:9px 0; border-bottom:1px solid var(--rule); color:var(--ink2); }}
td:first-child {{ color:var(--ink); }}
td.sm {{ font-size:11px; }}
tr:last-child td {{ border-bottom:none; }}
th + th, td + td {{ padding-left:16px; }}

footer {{ margin-top:52px; padding-top:20px; border-top:1px solid var(--rule);
  font-size:13px; color:var(--ink3); }}
a {{ color:var(--accent); }}
a:focus-visible, .tile:focus-visible {{ outline:2px solid var(--accent); outline-offset:3px; }}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none!important; transition:none!important; }} }}
</style>

<div class="wrap">
<header>
  <h1>NYC Taxi Operations</h1>
  <p class="lede">A static snapshot of the Gold marts — 20 business KPIs built from 1,458,644 raw
  trips through a governed Bronze → Silver → Gold pipeline on Databricks.</p>
  <div class="prov">
    <span><b>run</b> {run_id}</span>
    <span><b>source</b> {source_file}</span>
    <span><b>sha256</b> {source_hash}…</span>
    <span><b>rendered</b> {generated}</span>
  </div>
</header>

<section>
  <h2>Reconciliation</h2>
  <div class="recon">
    <p class="eq"><span class="v">{valid}</span> valid <span class="op">+</span>
      <span class="q">{quar}</span> quarantined <span class="op">=</span> {total} ingested</p>
    <p class="note">Nothing was deleted to make a number behave. Every rejected row sits in
    <span class="mono">silver_trips_quarantine</span> carrying the rule id that rejected it, and
    this identity is asserted as a test on every build — if it ever stops holding, the pipeline
    fails rather than quietly shipping a smaller population.</p>
  </div>
</section>

<section>
  <h2>Business KPIs</h2>
  <div class="tiles">{tiles}</div>
  <p class="note">Distance and speed are <strong>estimated</strong> — geodesic straight-line
  between pickup and drop-off, never road distance, so both understate a real route by a factor
  that varies with the route. KPI-016 and KPI-017 shipped withheld and were released only once
  their thresholds had distribution evidence and a named approver; KPI-017 is an
  anomaly-candidate rate, not a congestion rate.</p>
</section>

<section>
  <h2>Demand</h2>
  <div class="panel">{daily}</div>
  <div class="two" style="margin-top:16px">
    <div class="panel"><h3>Trips by hour of day</h3>{hourly}</div>
    <div class="panel"><h3>Top pickup areas</h3><div style="margin-top:14px">{pickup}</div></div>
  </div>
</section>

<section>
  <h2>Geography</h2>
  <div class="two">
    <div class="panel"><h3>Top drop-off areas</h3><div style="margin-top:14px">{dropoff}</div></div>
    <div class="panel"><h3>Top routes</h3><div class="scroll" style="margin-top:12px"><table>
      <thead><tr><th>Route</th><th>Trips</th><th>Avg</th><th>P50</th><th>P90</th><th>Est. km</th>
      <th>Est. km/h</th></tr></thead><tbody>{route_rows}</tbody></table></div></div>
  </div>
  <p class="note">Pickup and drop-off areas carry a trip count and nothing else: KPI-010 and
  KPI-011 are defined as a count, and only routes carry companion duration and distance metrics.
  Showing an empty duration column for areas would look like broken data rather than a
  definition.</p>
</section>

<section>
  <h2>Vendor comparison</h2>
  <div class="panel scroll"><table>
    <thead><tr><th>Vendor</th><th>Trips</th><th>Share</th><th>Avg min</th><th>P50 min</th>
    <th>P90 min</th><th>Est. km</th><th>Est. km/h</th></tr></thead>
    <tbody>{vendor_rows}</tbody></table></div>
  <p class="note">P50 and P90 sit beside the mean deliberately. Trip durations are right-skewed
  and the two vendors' trip mixes differ, so comparing averages alone invites "vendor 2 is
  slower" — a conclusion this data does not support.</p>
</section>

<section>
  <h2>Data quality</h2>
  <div class="two">
    <div class="panel"><h3>Component scores</h3><div style="margin-top:14px">{meters}</div>
      <p class="note">Shown separately rather than blended into one number: a single score hides
      which dimension is failing, which is the one thing an operator needs to know.</p></div>
    <div class="panel"><h3>Quarantine by rule</h3><div class="scroll" style="margin-top:12px">
      <table><thead><tr><th>Rule</th><th>Reason</th><th>Rows</th><th>% of batch</th></tr></thead>
      <tbody>{quar_rows}</tbody></table></div>
      <p class="note">Invalid rate {invalid}% · duplicate rate {dup}%. Both coordinate rules
      reject to quarantine; outliers such as a 41-day trip duration are flagged and kept,
      because a statistically extreme trip is not automatically an invalid one.</p></div>
  </div>
</section>

<footer>
  Generated by <span class="mono">scripts/generate_dashboard_snapshot.py</span> from the live
  Gold marts. This is a snapshot, not a live view — the interactive Databricks AI/BI dashboard
  is not publicly shareable, since Databricks requires every viewer to be registered with the
  account.
</footer>
</div>
"""


def main():
    ap = argparse.ArgumentParser(description="Render a shareable snapshot of the Gold marts.")
    ap.add_argument("--from", dest="cache", help="render from a saved JSON pull instead of querying")
    ap.add_argument("--dump", help="also write the raw pull to this path")
    a = ap.parse_args()

    data = json.loads(pathlib.Path(a.cache).read_text(encoding="utf-8")) if a.cache else pull()
    if a.dump:
        pathlib.Path(a.dump).write_text(json.dumps(data, indent=1), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
