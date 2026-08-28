#!/usr/bin/env python3
"""
check_lineage.py — verify every KPI can be traced from source column to consumer, and scaffold
the blocks that are missing.

KPI contract §17 requires a lineage chain per Gold KPI:

    Source Column -> Silver Derived Column -> Transformation -> Gold Metric -> Consumer

The point is answerable questions. When someone asks "where does this number come from?", the
answer should be a document, not an afternoon of reading SQL. A KPI whose lineage nobody can
state is a KPI nobody can defend.

Usage:
    check_lineage.py                 # report coverage
    check_lineage.py --strict        # fail when a KPI has no lineage block
    check_lineage.py --scaffold      # print skeleton blocks for the KPIs that lack one
    check_lineage.py --kpi KPI-005   # scaffold one KPI

Exit codes: 0 = complete (or advisory) · 1 = violation · 2 = usage/environment error
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check_lineage: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

KPI_CONFIG = "configs/kpi_config.yml"
LINEAGE_DOC = "docs/architecture/kpi-lineage.md"

# The five stages every chain must name.
STAGES = ("source", "silver", "transformation", "gold", "consumer")

# Silver derived columns (spec §5) mapped to the source columns and transformation that
# produce them. Inference is a starting point for a human to check, not a claim of truth.
DERIVED = {
    "estimated_distance_km": (["pickup_latitude", "pickup_longitude",
                               "dropoff_latitude", "dropoff_longitude"],
                              "Haversine transformation (Earth radius 6371 km)"),
    "estimated_speed_kmh": (["pickup_latitude", "pickup_longitude", "dropoff_latitude",
                             "dropoff_longitude", "trip_duration"],
                            "estimated_distance_km / (trip_duration / 3600)"),
    "pickup_date": (["pickup_datetime"], "DATE(pickup_datetime)"),
    "pickup_hour": (["pickup_datetime"], "HOUR(pickup_datetime)"),
    "pickup_area": (["pickup_latitude", "pickup_longitude"],
                    "coordinate bucketing (zone polygons deferred — contract §8)"),
    "dropoff_area": (["dropoff_latitude", "dropoff_longitude"],
                     "coordinate bucketing (zone polygons deferred — contract §8)"),
    "route_key": (["pickup_latitude", "pickup_longitude",
                   "dropoff_latitude", "dropoff_longitude"],
                  "pickup_area || ' -> ' || dropoff_area"),
    "trip_duration_minutes": (["trip_duration"], "trip_duration / 60"),
    "is_valid_trip": (["id", "vendor_id", "pickup_datetime", "dropoff_datetime",
                       "passenger_count", "coordinates", "trip_duration"],
                      "DQ-001..DQ-013 evaluated per row"),
    "is_duration_outlier": (["trip_duration"],
                            "trip_duration > thresholds.extreme_duration_seconds (flag, never delete)"),
    "is_speed_outlier": (["pickup_latitude", "pickup_longitude", "dropoff_latitude",
                          "dropoff_longitude", "trip_duration"],
                         "estimated_speed_kmh outside approved bounds (flag, never delete)"),
    "vendor_id": (["vendor_id"], "passthrough, validated by DQ-003"),
    "trip_duration": (["trip_duration"], "passthrough, validated by DQ-007"),
    "id": (["id"], "passthrough, deduplicated per DQ-002"),
}

# KPIs whose lineage runs through the data-quality audit rather than a trip column.
AUDIT_LINEAGE = {
    "KPI-018": (["all source columns"], "silver_trips + silver_trips_quarantine",
                "valid_records / total_records — evaluated over ALL source records"),
    "KPI-019": (["all source columns"], "silver_trips_quarantine",
                "invalid_records / total_records — the complement of KPI-018"),
    "KPI-020": (["id"], "duplicate audit table",
                "duplicate_records / total_records — read from the PRE-deduplication count"),
}

# Order matters: the most specific derived column a KPI touches is the one to name.
DERIVED_PRIORITY = [
    "estimated_speed_kmh", "estimated_distance_km", "route_key", "pickup_area", "dropoff_area",
    "is_speed_outlier", "is_duration_outlier", "pickup_date", "pickup_hour",
    "trip_duration_minutes", "vendor_id", "trip_duration", "is_valid_trip", "id",
]

CONSUMER_BY_DOMAIN = {
    "trip_performance": "Executive dashboard — trip performance tiles",
    "operational_efficiency": "Operations dashboard",
    "demand": "Executive dashboard — demand trend",
    "geography": "Executive dashboard — top areas / top routes",
    "vendor": "Vendor performance report",
    "operations": "Operations dashboard — anomaly rates",
    "data_quality": "Data quality dashboard; pipeline run report",
}


def strip_code_fences(text):
    """A template in the docs is not a filled-in lineage block."""
    out, fenced = [], False
    for line in (text or "").split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def block_for(text, kpi_id):
    """Return the lineage block for a KPI id, or None."""
    if not text:
        return None
    lines = strip_code_fences(text).split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#") and kpi_id in ln:
            start = i
            break
    if start is None:
        return None
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    body = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.lstrip().startswith("#"):
            lvl = len(ln) - len(ln.lstrip("#"))
            if lvl <= level:
                break
        body.append(ln)
    return "\n".join(body)


def infer_lineage(kpi):
    """Return (source_columns, silver_column, derivation_label)."""
    if kpi["id"] in AUDIT_LINEAGE:
        src, col, label = AUDIT_LINEAGE[kpi["id"]]
        return src, col, label
    haystack = " ".join(str(kpi.get(f, "")) for f in
                        ("formula", "grain", "filter", "dimensions", "threshold_ref"))
    for col in DERIVED_PRIORITY:
        if re.search(rf"\b{re.escape(col)}\b", haystack):
            src, label = DERIVED[col]
            return src, col, label
    return ["<source column>"], "<silver derived column>", "<derivation>"


def scaffold(kpi):
    sources, col, label = infer_lineage(kpi)
    consumer = CONSUMER_BY_DOMAIN.get(kpi.get("domain"), "<consumer>")
    caveat = kpi.get("caveat") or kpi.get("interpretation_caveat")
    out = [
        f"### {kpi['id']} — {kpi.get('name')}",
        "",
        "```text",
        "\n".join(sources),
        "        |",
        f"        v   {label}",
        col,
        "        |",
        f"        v   {kpi.get('formula')}",
        f"{kpi['id']} {kpi.get('name')}   ->   {kpi.get('mart')}",
        "        |",
        "        v",
        consumer,
        "```",
        "",
        f"- **Source:** {', '.join(sources)}",
        f"- **Silver:** {col} — {label}",
        f"- **Transformation:** {kpi.get('formula')}",
        f"- **Gold:** {kpi.get('mart')} · grain {kpi.get('grain')} · filter `{kpi.get('filter')}`",
        f"- **Consumer:** {consumer}",
    ]
    if caveat:
        out.append(f"- **Caveat:** {' '.join(str(caveat).split())}")
    if kpi.get("threshold_ref"):
        out.append(f"- **Depends on threshold:** `{kpi['threshold_ref']}` "
                   f"({kpi.get('threshold_status', 'unknown')})")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Check and scaffold KPI lineage documentation.")
    ap.add_argument("--strict", action="store_true", help="fail when a KPI has no lineage block")
    ap.add_argument("--scaffold", action="store_true", help="print skeletons for missing KPIs")
    ap.add_argument("--kpi", help="scaffold a single KPI id")
    ap.add_argument("--quiet", action="store_true", help="only print on failure")
    args = ap.parse_args()

    cfg = Path(KPI_CONFIG)
    if not cfg.exists():
        print(f"check_lineage: {KPI_CONFIG} not found", file=sys.stderr)
        return 2
    doc = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    kpis = [k for k in (doc.get("kpis") or []) if isinstance(k, dict)]

    if args.kpi:
        match = next((k for k in kpis if k.get("id") == args.kpi), None)
        if not match:
            print(f"check_lineage: no KPI {args.kpi}", file=sys.stderr)
            return 2
        print(scaffold(match))
        return 0

    lpath = Path(LINEAGE_DOC)
    ltext = lpath.read_text(encoding="utf-8") if lpath.exists() else None

    complete, incomplete, missing = [], [], []
    for k in kpis:
        block = block_for(ltext, k["id"])
        if block is None:
            missing.append(k)
            continue
        low = block.lower()
        absent = [st for st in STAGES if st not in low]
        # A block carrying an unfilled <placeholder> is not documented lineage, however many
        # stage labels it has. Checking only for the labels would pass a template.
        if re.search(r"<[a-z][a-z _-]*>", block, re.I):
            absent = absent + ["unfilled placeholder"]
        (incomplete if absent else complete).append((k, absent))

    if args.scaffold:
        if not missing:
            print(f"All {len(kpis)} KPIs already have a lineage block in {LINEAGE_DOC}.")
            return 0
        print(f"<!-- scaffold for {len(missing)} KPI(s) missing from {LINEAGE_DOC} -->\n")
        for k in missing:
            print(scaffold(k))
        return 0

    if not args.quiet:
        if ltext is None:
            print(f"{LINEAGE_DOC} does not exist yet — 0/{len(kpis)} KPIs documented.")
            print("Run with --scaffold to generate the skeleton blocks.")
        else:
            print(f"Lineage coverage: {len(complete)}/{len(kpis)} complete.")
            for k, absent in incomplete:
                print(f"  · {k['id']} block present but missing stage(s): {', '.join(absent)}")
            if missing:
                print(f"  · no block: {', '.join(k['id'] for k in missing)}")

    if args.strict and (missing or incomplete):
        print(f"\nBLOCKED  {len(missing) + len(incomplete)} KPI(s) lack a complete lineage chain "
              f"(contract §17).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
