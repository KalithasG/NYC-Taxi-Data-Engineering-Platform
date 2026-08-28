#!/usr/bin/env python3
"""
check_profiling_complete.py — decide whether a profiling run may be called finished.

"Profiling is done" is the claim that unblocks six thresholds, two KPIs and the whole Silver
layer. It is worth being hard to say. Profiling spec §33 lists 19 success criteria and §29 lists
six output tables; this checks the report against both, plus the run metadata that makes the run
reproducible at all.

Usage:
    check_profiling_complete.py                 # check the default report
    check_profiling_complete.py --report PATH
    check_profiling_complete.py --quiet

Exit codes: 0 = complete · 1 = incomplete · 2 = usage/environment error
"""

import argparse
import re
import sys
from pathlib import Path

REPORT = "docs/profiling/profiling-report.md"

# Profiling spec §29 — the six datasets a run must emit.
OUTPUT_TABLES = (
    "profile_run", "profile_schema", "profile_numeric_stats",
    "profile_domain_stats", "profile_quality", "profile_anomalies",
)

# Profiling spec §4 — without these a run cannot be reproduced or audited.
RUN_METADATA = (
    "profiling_run_id", "source_file", "source_hash",
    "profiling_timestamp", "row_count", "column_count", "profile_status",
)

# Profiling spec §33 — the 19 criteria, keyed by a phrase that must appear addressed.
SUCCESS_CRITERIA = (
    ("schema validated", ("schema",)),
    ("completeness statistics", ("completeness", "null rate", "null_rate")),
    ("primary-key uniqueness", ("uniqueness", "unique")),
    ("duplicate categories", ("duplicate",)),
    ("timestamp ranges", ("timestamp", "date range")),
    ("temporal distributions", ("temporal", "hour", "day of week", "day_of_week")),
    ("coordinate distributions", ("coordinate",)),
    ("geographic anomalies quantified", ("geographic", "geo-")),
    ("trip-duration distribution", ("duration",)),
    ("distance distribution", ("distance",)),
    ("speed distribution", ("speed",)),
    ("vendor distributions compared", ("vendor",)),
    ("store-and-forward profiled", ("store", "store_and_fwd")),
    ("cross-field inconsistencies", ("cross-field", "consistency", "duration_difference")),
    ("hard-invalid records identified", ("invalid",)),
    ("outliers identified not deleted", ("outlier",)),
    ("KPI thresholds proposed", ("threshold",)),
    ("results reproducible", ("reproduc", "source_hash")),
    ("artifacts version-controlled", ("version-control", "version control", "git")),
)

PLACEHOLDER = re.compile(r"_pending_|<pending>|\bTBD\b|XXX|TODO", re.IGNORECASE)


def strip_code_fences(text):
    """Ignore fenced blocks — a template showing the required headings is not a filled-in report."""
    out, fenced = [], False
    for line in (text or "").split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Verify a profiling run meets spec §33 before it counts as done.")
    ap.add_argument("--report", default=REPORT, help=f"path to the profiling report (default {REPORT})")
    ap.add_argument("--quiet", action="store_true", help="only print on failure")
    args = ap.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"BLOCKED  {args.report} does not exist. Profiling has not been run.", file=sys.stderr)
        return 1

    raw = path.read_text(encoding="utf-8")
    text = strip_code_fences(raw)
    low = text.lower()
    problems = []

    # Is this still the stub?
    if re.search(r"^\*\*status:\*\*\s*not yet run", text, re.IGNORECASE | re.MULTILINE):
        problems.append("report is still marked NOT YET RUN — it is the required structure, "
                        "not a completed run.")

    # Run metadata must be filled in, not placeholders.
    for field in RUN_METADATA:
        if field not in low:
            problems.append(f"run metadata missing: {field}")
        else:
            for line in text.split("\n"):
                if field in line.lower() and PLACEHOLDER.search(line):
                    problems.append(f"run metadata {field} is still a placeholder")
                    break

    # A source hash that is not a real digest makes the run unreproducible.
    if not re.search(r"\b[0-9a-f]{64}\b", text, re.IGNORECASE):
        problems.append("no SHA256 source hash recorded — the run cannot be reproduced "
                        "or tied to a specific input file (spec §4).")

    # The six output datasets.
    missing_tables = [t for t in OUTPUT_TABLES if t not in low]
    if missing_tables:
        problems.append(f"output tables not referenced: {', '.join(missing_tables)} (spec §29)")

    # The 19 success criteria.
    unmet = [label for label, keys in SUCCESS_CRITERIA
             if not any(k.lower() in low for k in keys)]
    if unmet:
        problems.append(f"{len(unmet)} of 19 success criteria unaddressed (spec §33): "
                        + "; ".join(unmet))

    # A finished report proposes thresholds with evidence.
    if "threshold" in low and not re.search(r"p(50|75|90|95|99)", low):
        problems.append("thresholds discussed without percentile evidence — spec §30 requires "
                        "candidate thresholds backed by actual distributions.")

    if problems:
        print(f"BLOCKED  {args.report} is not a completed profiling run:", file=sys.stderr)
        for p in problems:
            print(f"         - {p}", file=sys.stderr)
        print("\nSee .claude/skills/data-profiling-runner/SKILL.md for the execution order.",
              file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK — {args.report} satisfies spec §33 (19 criteria) and §29 (6 output tables).")
        print("     Thresholds may now be proposed via the threshold-decision skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
