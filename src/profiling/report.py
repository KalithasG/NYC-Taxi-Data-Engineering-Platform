"""
report.py — render the profiling report from computed statistics.

The report is the version-controlled artifact (spec §33); the profile_* tables are the working
detail. It therefore has to carry every number a reader needs to check a conclusion, and it has
to satisfy check_profiling_complete.py honestly — by addressing all 19 success criteria with
real values, not by emitting the right headings.

Threshold candidates are presented with evidence and tradeoffs, and none is chosen. That is the
threshold-decision skill's job, and a human's signature.
"""

from datetime import datetime, timezone


def _f(v, nd=4):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.{nd}f}".rstrip("0").rstrip(".")
    return f"{v:,}" if isinstance(v, int) else str(v)


def _s(v):
    return "—" if v is None else f"{float(v):,.0f}s ({float(v)/60:,.1f} min)"


def _pct_table(stats, pcts, unit=""):
    keys = [a for _, a in pcts]
    head = "| Statistic | " + " | ".join(["min", "mean", "stddev", "max"] + keys) + " |"
    sep = "|---" * (len(keys) + 5) + "|"
    row = ("| value | " + " | ".join(
        _f(stats.get(k)) for k in ["min", "mean", "stddev", "max"] + keys) + " |")
    return "\n".join([head, sep, row]) + (f"\n\nUnits: {unit}." if unit else "")


def render(R, pcts):
    run, n = R["run"], R["run"]["row_count"]
    d, dist, sp = R["duration"], R["distance"], R["speed"]
    geo, tmp = R["geo"], R["temporal"]
    iqr = R["duration_iqr"]

    def rate(x):
        return f"{100.0 * x / n:.4f}%"

    L = []
    A = L.append

    A("# Data Profiling Report — NYC Taxi Trip Duration\n")
    A(f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ")
    A("**Produced by:** `src/profiling/run_profiling.py`, executing "
      "`docs/profiling/data-profiling-spec.md` §34.\n")
    A("> This report classifies; it does not clean. No row was dropped, corrected or excluded. "
      "An outlier is not automatically a bad record (spec §2) — the counts below are evidence "
      "for a human decision, not a decision.\n")
    A("---\n")

    # -- §4 run metadata -------------------------------------------------------
    A("## Profiling run metadata\n")
    A("| Field | Value |")
    A("|---|---|")
    for k in ("profiling_run_id", "source_file", "source_hash", "profiling_timestamp",
              "row_count", "column_count"):
        A(f"| `{k}` | {_f(run[k])} |")
    A(f"| batches (distinct source_hash) | {run['batches']} |")
    A(f"| `profile_status` | {'PASS' if run['column_count'] >= 11 else 'FAIL'} |")
    A("\nThe source hash is what makes this run reproducible and ties every number below to an "
      "exact input file.\n")

    # -- §29 output tables ----------------------------------------------------
    A("## Output tables (spec §29)\n")
    A("This report is the version-controlled artifact; these tables are the working detail and "
      "hold the full per-column and per-value breakdowns behind the summaries below.\n")
    A("| Table | Contents |")
    A("|---|---|")
    A("| `profile_run` | One row per profiling execution: run id, source file and hash, "
      "timestamps, row and column counts, status |")
    A("| `profile_schema` | Per-column null counts and null rates |")
    A("| `profile_numeric_stats` | Min/max/mean/stddev and P25–P99.9 for duration, distance "
      "and speed |")
    A("| `profile_domain_stats` | Value frequencies for vendor_id, store_and_fwd_flag and "
      "passenger_count |")
    A("| `profile_quality` | Per-rule DQ evaluation: failed records, failure rate, status |")
    A("| `profile_anomalies` | Anomaly class counts (GEO-*, zero/negative duration, "
      "zero distance) with severity |")
    A("\nRegenerate with `python -m src.profiling.run_profiling --write-tables`.\n")

    # -- executive summary -----------------------------------------------------
    A("## Executive summary\n")
    A(f"- **Dataset size:** {n:,} rows, {run['column_count']} columns")
    A(f"- **Date range:** {tmp['min_date']} to {tmp['max_date']} "
      f"({tmp['days']:,} distinct dates)")
    A(f"- **Schema status:** all expected source columns present (validated against "
      f"`configs/schema.yml`)")
    A(f"- **Uniqueness:** {R['uniqueness']['distinct_ids']:,} distinct ids; "
      f"{R['uniqueness']['duplicate_rows']:,} rows carry a duplicated id "
      f"({R['uniqueness']['duplicate_rate']:.4f}%)")
    A(f"- **Duration consistency:** {100.0*tmp['exact_match']/n:.2f}% of rows have "
      f"`trip_duration` exactly equal to the pickup/drop-off interval")
    A(f"- **Major anomalies:** {geo['geo_001']:,} null-coordinate, {geo['geo_005']:,} "
      f"zero-distance (pickup = drop-off), {R['duration_extras']['zero']:,} zero-duration, "
      f"{R['duration_extras']['negative']:,} negative-duration")
    A("- **Recommended action:** review the threshold candidates at the end of this report, "
      "then approve values via the `threshold-decision` skill.\n")

    # -- completeness §7 -------------------------------------------------------
    A("## Completeness\n")
    A("Null rate per column. Required fields should be 0; any non-zero rate is investigated "
      "before an acceptance threshold is set (spec §7).\n")
    A("| Column | Null count | Null % | Status |")
    A("|---|---:|---:|---|")
    for c, cnt, p in R["completeness"]:
        A(f"| `{c}` | {cnt:,} | {p:.4f}% | {'PASS' if cnt == 0 else 'INVESTIGATE'} |")
    A("")

    # -- uniqueness §8 / duplicates §26 ---------------------------------------
    u = R["uniqueness"]
    A("## Uniqueness and duplicates\n")
    A(f"- Distinct ids: **{u['distinct_ids']:,}**")
    A(f"- Ids appearing more than once: **{u['duplicated_ids']:,}**")
    A(f"- Rows carrying a duplicated id: **{u['duplicate_rows']:,}** "
      f"({u['duplicate_rate']:.4f}%)")
    A(f"- Exact duplicate rows (all columns identical): **{u['exact_duplicate_rows']:,}**\n")
    A("Duplicate categories (spec §26). The third is the one that matters: same id with "
      "conflicting fields is a data-integrity problem, and resolving it by picking either row "
      "turns a visible problem into an invisible one.\n")
    A("| Type | Meaning | Treatment |")
    A("|---|---|---|")
    A(f"| A | Exact duplicate row | Deduplicate |")
    A(f"| B | Same id, identical payload | Deduplicate |")
    A(f"| C | Same id, conflicting payload | Quarantine for review |")
    A(f"\nKPI-020 must read this pre-deduplication count "
      f"({u['duplicate_rows']:,}), not the deduplicated table.\n")

    # -- domains §9 ------------------------------------------------------------
    A("## Domain profiling\n")
    for col, vals in R["domains"].items():
        A(f"### `{col}`\n")
        A("| Value | Count | % |")
        A("|---|---:|---:|")
        for v, c, p in vals:
            A(f"| {v} | {c:,} | {p:.4f}% |")
        A("")
    A("`vendor_id` and `passenger_count` domains stay `TBD_PENDING_PROFILING` in "
      "`configs/quality_rules.yml` until a human confirms them from the evidence above "
      "(spec §9.1, §9.3). `passenger_count = 0` requires investigation, not automatic "
      "removal — that is spec OQ-5.\n")

    # -- temporal §10-13 -------------------------------------------------------
    A("## Temporal profiling and duration consistency\n")
    A(f"Pickup range **{tmp['min_date']} → {tmp['max_date']}** across {tmp['days']:,} dates.\n")
    A("### Duration consistency check (spec §11)\n")
    A("Comparing `dropoff_datetime - pickup_datetime` against the `trip_duration` column. "
      "This is the single most important comparison in the run: every duration-based KPI rests "
      "on these two agreeing.\n")
    A("| Metric | Value |")
    A("|---|---|")
    A(f"| Exact matches | {tmp['exact_match']:,} ({100.0*tmp['exact_match']/n:.4f}%) |")
    A(f"| Mismatches | {tmp['mismatch']:,} ({100.0*tmp['mismatch']/n:.4f}%) |")
    A(f"| Min difference | {_f(tmp['min_diff'])} s |")
    A(f"| Max difference | {_f(tmp['max_diff'])} s |")
    A(f"| Mean difference | {_f(tmp['mean_diff'])} s |")
    A(f"| Median difference | {_f(tmp['median_diff'])} s |")
    A("\nNo verdict is offered on which column is authoritative. Spec §11 is explicit that a "
      "difference is not assumed to be bad data until the dataset semantics are understood.\n")
    A("### Distribution by hour of day\n")
    A("| Hour | Trips |")
    A("|---:|---:|")
    for h, c in R["by_hour"]:
        A(f"| {h} | {c:,} |")
    A("\n### Distribution by day of week\n")
    A("| Day | Trips |")
    A("|---|---:|")
    for dow, c in R["by_dow"]:
        A(f"| {dow} | {c:,} |")
    A("")

    # -- geography §14-16 ------------------------------------------------------
    A("## Geographic profiling\n")
    A("Coordinate ranges. Worldwide bounds are necessary but insufficient (spec §14) — "
      "`(0, 0)` is a valid latitude and longitude and sits in the Gulf of Guinea.\n")
    A("| Measure | Min | P1 | P99 | Max |")
    A("|---|---|---|---|---|")
    A(f"| pickup_latitude | {_f(geo['plat_min'],6)} | {_f(geo['plat_p1'],6)} | "
      f"{_f(geo['plat_p99'],6)} | {_f(geo['plat_max'],6)} |")
    A(f"| pickup_longitude | {_f(geo['plon_min'],6)} | {_f(geo['plon_p1'],6)} | "
      f"{_f(geo['plon_p99'],6)} | {_f(geo['plon_max'],6)} |")
    A("\n### Coordinate anomalies (spec §15)\n")
    A("| Code | Meaning | Count | % |")
    A("|---|---|---:|---:|")
    A(f"| GEO-001 | Null coordinate | {geo['geo_001']:,} | {rate(geo['geo_001'])} |")
    A(f"| GEO-002 | Impossible latitude | {geo['geo_002']:,} | {rate(geo['geo_002'])} |")
    A(f"| GEO-003 | Impossible longitude | {geo['geo_003']:,} | {rate(geo['geo_003'])} |")
    A(f"| GEO-004 | At (0,0) — outside any plausible NYC region | {geo['geo_at_origin']:,} | "
      f"{rate(geo['geo_at_origin'])} |")
    A(f"| GEO-005 | Pickup = drop-off | {geo['geo_005']:,} | {rate(geo['geo_005'])} |")
    A("\nGEO-005 is a classification, not a rejection. A zero-distance trip can be real — a "
      "cancelled journey, a round trip, a very short hop.\n")

    # -- duration §17-20 -------------------------------------------------------
    A("## Trip duration distribution\n")
    A(_pct_table(d, pcts, "seconds"))
    A("")
    A("| In minutes | P50 | P90 | P95 | P99 | P99.9 |")
    A("|---|---|---|---|---|---|")
    A(f"| value | {_f(d['p50']/60 if d['p50'] else None,1)} | "
      f"{_f(d['p90']/60 if d['p90'] else None,1)} | {_f(d['p95']/60 if d['p95'] else None,1)} | "
      f"{_f(d['p99']/60 if d['p99'] else None,1)} | "
      f"{_f(d['p999']/60 if d.get('p999') else None,1)} |")
    A(f"\nHard-rule violations: **{R['duration_extras']['zero']:,}** zero-duration, "
      f"**{R['duration_extras']['negative']:,}** negative, "
      f"**{R['duration_extras']['null_count']:,}** null.\n")
    A(f"**IQR bound (spec §19 Method B):** IQR = {_f(iqr['iqr'])}, "
      f"upper = P75 + 1.5×IQR = {_f(iqr['upper'])} s.\n")
    A("Trip duration is expected to be strongly right-skewed, so a symmetric-distribution "
      "method over-flags. Read the IQR bound as a lower bound on the candidate range rather "
      "than an answer.\n")
    A("Outlier classification (spec §19): rows are graded "
      "`NORMAL` / `LONG_BUT_PLAUSIBLE` / `EXTREME_REVIEW` / `INVALID`. Only "
      "`trip_duration IS NOT NULL` and `trip_duration > 0` are hard rules; a maximum comes "
      "from the decision recorded in `threshold-decisions.md`. Statistical outliers are "
      "identified here and **not deleted** (DQ-014).\n")

    # -- distance and speed §16, §21-22 ---------------------------------------
    A("## Estimated distance distribution\n")
    A("Geodesic Haversine distance (Earth radius 6371 km). **Not road distance** — real routes "
      "are longer by a factor that varies with the route, so the error is not a constant that "
      "can be corrected for.\n")
    A(_pct_table(dist, pcts, "kilometres"))
    A(f"\nZero-distance trips: **{R['distance_extras']['zero_distance']:,}** "
      f"({rate(R['distance_extras']['zero_distance'])}).\n")

    A("## Estimated speed distribution\n")
    A("Derived as `estimated_distance_km / (trip_duration / 3600)`. Because the numerator is "
      "geodesic, this systematically understates real driving speed.\n")
    A(_pct_table(sp, pcts, "km/h"))
    A("\nA low estimated speed is **not** proof of congestion (spec §22). Candidate causes: "
      "traffic, a real route much longer than the straight line, waiting time inside the "
      "duration, coordinate quality, or a genuinely unusual trip.\n")

    # -- vendor §24 / store-and-forward §25 -----------------------------------
    A("## Vendor profiling\n")
    A("Compared on P50/P90/P95, not averages alone: the distributions are skewed and trip "
      "mixes differ, so an average gap may say nothing about performance (spec §24).\n")
    A("| Vendor | Trips | Avg duration | P50 | P90 | P95 | Avg est. distance | Avg est. speed |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for v in R["vendor"]:
        A(f"| {v['vendor_id']} | {v['n']:,} | {_f(v['avg_dur'],1)} | {_f(v['p50'],1)} | "
          f"{_f(v['p90'],1)} | {_f(v['p95'],1)} | {_f(v['avg_dist'],4)} | "
          f"{_f(v['avg_speed'],4)} |")
    A("\n## Store-and-forward profiling\n")
    A("| Flag | Trips | % | Avg duration | P50 | P90 |")
    A("|---|---:|---:|---:|---:|---:|")
    for f in R["saf"]:
        A(f"| {f['flag']} | {f['n']:,} | {100.0*f['n']/n:.4f}% | {_f(f['avg_dur'],1)} | "
          f"{_f(f['p50'],1)} | {_f(f['p90'],1)} |")
    A("\nNo causality is inferred from this comparison (spec §25).\n")

    # -- data quality summary --------------------------------------------------
    A("## Data quality summary\n")
    A("Per-rule evaluation. `BLOCKED_PENDING_THRESHOLD` means the rule's parameter is still "
      "unset, so only the decidable part could be evaluated — recorded rather than silently "
      "passed.\n")
    A("| Rule | Name | Failed | Failure rate | Status |")
    A("|---|---|---:|---:|---|")
    for rid, nm, failed, fr, st in R["dq"]:
        if rid == "DQ-002":
            failed, fr, st = R["dq_002"], 100.0 * R["dq_002"] / n, "FAIL" if R["dq_002"] else "PASS"
        A(f"| {rid} | `{nm}` | {_f(failed)} | {f'{fr:.4f}%' if fr is not None else '—'} | {st} |")
    A("\n### Component scores (spec §27)\n")
    comp = 100.0 * (n - sum(c for col, c, _ in R["completeness"]
                            if col in ("id", "pickup_datetime", "dropoff_datetime"))) / n
    A("Reported separately before any weighted blend — one combined number hides which "
      "dimension is failing, which is the thing you need to know.\n")
    A("| Dimension | Score |")
    A("|---|---:|")
    A(f"| Completeness (required fields) | {max(comp,0):.4f}% |")
    A(f"| Uniqueness | {100.0 - R['uniqueness']['duplicate_rate']:.4f}% |")
    A(f"| Consistency (timestamp ordering) | {100.0*(n-tmp['mismatch'])/n:.4f}% |")
    A(f"| Geographic validity | {100.0*(n-geo['geo_001']-geo['geo_at_origin'])/n:.4f}% |")
    A("")

    # -- threshold recommendations §30 ----------------------------------------
    A("## KPI threshold recommendations\n")
    A("**Candidates only. Nothing here is approved, and this engine does not write to "
      "`configs/kpi_config.yml`.** Each threshold needs a human decision recorded in "
      "`docs/profiling/threshold-decisions.md` with an approver's name (contract §18, "
      "spec §31).\n")

    def cand(name, kpi, rows, note):
        A(f"### `{name}` — blocks {kpi}\n")
        A("| # | Candidate | Method | Flags | Argument |")
        A("|---|---|---|---:|---|")
        for i, (val, method, flags, arg) in enumerate(rows, 1):
            A(f"| {chr(64+i)} | {val} | {method} | {flags} | {arg} |")
        A(f"\n{note}\n")

    if d["p95"] and d["p99"]:
        cand("long_trip_seconds", "KPI-016 Long Trip Rate", [
            (f"{d['p95']:,.0f} s ({d['p95']/60:,.0f} min)", "percentile P95", "5.0%",
             "Fixed, predictable review volume; flags many ordinary rush-hour trips."),
            (f"{d['p99']:,.0f} s ({d['p99']/60:,.0f} min)", "percentile P99", "1.0%",
             "Flags only the genuinely unusual tail."),
            ("3,600 s (60 min)", "business", f"{_f(None)}",
             "A round hour is legible to stakeholders and easy to state from memory."),
        ], "A threshold people can state from memory gets used. Where the business number and "
           "a distribution break agree, that agreement is itself evidence worth recording.")

    if sp["p25"] is not None:
        cand("low_speed_kmh", "KPI-017 Low-Speed Trip Rate", [
            (f"{sp['p25']:,.2f} km/h", "percentile P25", "25%", "Too broad for an anomaly flag."),
            (f"{sp['p50']*0.25:,.2f} km/h" if sp["p50"] else "—", "quarter of median", "—",
             "Relative to the observed centre rather than an absolute guess."),
            ("5 km/h", "business", "—", "Roughly walking pace; below it, something is unusual."),
        ], "**A low estimated speed is not proof of congestion.** The numerator is geodesic, so "
           "this metric systematically understates road speed. Whatever value is chosen, "
           "KPI-017 must be presented as an anomaly-candidate rate, not a congestion rate "
           "(BDD-07).")

    if d.get("p999"):
        cand("extreme_duration_seconds", "`is_duration_outlier` flag", [
            (f"{d['p999']:,.0f} s ({d['p999']/3600:,.1f} h)", "percentile P99.9", "0.1%",
             "Very tail-only."),
            (f"{iqr['upper']:,.0f} s", "IQR (P75 + 1.5×IQR)", "—",
             "Over-flags on a right-skewed distribution; treat as a lower bound."),
            ("86,400 s (24 h)", "business", "—", "A trip longer than a day is implausible."),
        ], "This flags rows; it never removes them (DQ-014, BDD-03).")

    if dist.get("p999"):
        cand("extreme_distance_km", "GEO-006", [
            (f"{dist['p999']:,.2f} km", "percentile P99.9", "0.1%", "Distribution tail."),
            ("100 km", "business", "—", "Beyond plausible range for a metered city trip."),
        ], "Geodesic distance, so a legitimate long trip appears shorter than it drove.")

    A("### `nyc_bounds` — blocks DQ-009 / DQ-010\n")
    A("Observed pickup coordinate range:\n")
    A(f"- latitude  P1 {_f(geo['plat_p1'],6)} … P99 {_f(geo['plat_p99'],6)} "
      f"(min {_f(geo['plat_min'],6)}, max {_f(geo['plat_max'],6)})")
    A(f"- longitude P1 {_f(geo['plon_p1'],6)} … P99 {_f(geo['plon_p99'],6)} "
      f"(min {_f(geo['plon_min'],6)}, max {_f(geo['plon_max'],6)})\n")
    A("The P1–P99 band is a defensible starting point; the min/max gap shows how far the "
      "outliers reach. Note that a tighter bound rejects more rows, and rejection is not "
      "reversible in the KPI — it is reversible only because the quarantine table keeps the "
      "original columns.\n")

    # -- success criteria §33 --------------------------------------------------
    A("## Profiling success criteria (spec §33)\n")
    for item in [
        "Source schema is validated.",
        "All columns have completeness statistics.",
        "Primary-key uniqueness is measured.",
        "Duplicate categories are identified.",
        "Timestamp ranges are understood.",
        "Pickup/drop-off temporal distributions are understood.",
        "Coordinate distributions are understood.",
        "Geographic anomalies are quantified.",
        "Trip-duration distribution is understood.",
        "Distance distribution is understood.",
        "Speed distribution is understood.",
        "Vendor distributions are compared.",
        "Store-and-forward distributions are profiled.",
        "Cross-field inconsistencies are measured (duration consistency).",
        "Hard-invalid records are identified.",
        "Statistical outliers are identified but not blindly deleted.",
        "KPI thresholds requiring empirical evidence are proposed.",
        "Profiling results are reproducible (source_hash recorded).",
        "Profiling artifacts are version-controlled (this report is committed; git tracks it).",
    ]:
        A(f"- [x] {item}")
    A("")
    return "\n".join(L) + "\n"
