#!/usr/bin/env python3
"""
check_layer_contracts.py — enforce the Bronze/Silver/Gold layer contracts in transformation code.

Three contracts, each guarding a specific failure:

  Bronze is append-only.   An UPDATE or DELETE against Bronze destroys the ability to reproduce
                           any downstream number from the original bytes.
  Silver is deterministic. current_timestamp(), rand() or an unordered LIMIT means two runs
                           disagree, which makes every KPI unfalsifiable (BDD-01/goal G2).
  Gold is idempotent.      A plain INSERT INTO a Gold mart double-counts on rerun (BDD-04).

Plus the wording rule from BDD-07: a coordinate-derived measure is geodesic, and must never be
presented as actual road distance or real driving speed.

Layer is inferred from the path (bronze/silver/gold) or the model name.

Usage:
    check_layer_contracts.py                # scan src/ and configs/
    check_layer_contracts.py --path src/transformations
    check_layer_contracts.py --staged       # only files staged for commit

Exit codes: 0 = clean · 1 = violation · 2 = usage/environment error
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCAN_DIRS = ("src", "configs")
CODE_SUFFIXES = {".sql", ".py"}

# Non-deterministic constructs. Same input must produce the same output, every run.
NONDETERMINISTIC = [
    (re.compile(r"\bcurrent_timestamp\b", re.I), "current_timestamp()"),
    (re.compile(r"\bcurrent_date\b", re.I), "current_date"),
    (re.compile(r"\bnow\s*\(", re.I), "now()"),
    (re.compile(r"\brand\s*\(|\brandom\s*\(", re.I), "rand()/random()"),
    (re.compile(r"\buuid\s*\(|\bgen_random_uuid\b", re.I), "uuid()"),
    (re.compile(r"\bmonotonically_increasing_id\s*\(", re.I), "monotonically_increasing_id()"),
    (re.compile(r"\bTABLESAMPLE\b", re.I), "TABLESAMPLE"),
]
# A LIMIT with no ORDER BY returns an arbitrary subset. ORDER BY precedes LIMIT in SQL, so
# the check looks for it anywhere in the statement — a lookahead after LIMIT flags every
# correctly-written query and none of the wrong ones.
HAS_LIMIT = re.compile(r"\bLIMIT\b", re.I)
HAS_ORDER_BY = re.compile(r"\bORDER\s+BY\b", re.I)

# Requires real SQL shape, not just the keyword. A bare \bUPDATE\b also matches Python
# method calls such as hashlib's h.update(chunk), which is not a Bronze mutation.
BRONZE_MUTATION = re.compile(
    r"\bUPDATE\s+[\w.`\"]+\s+SET\b"
    r"|\bDELETE\s+FROM\b"
    r"|\bMERGE\s+INTO\b"
    r"|\bTRUNCATE\s+TABLE\b"
    r"|\bINSERT\s+OVERWRITE\b", re.I)
GOLD_APPEND = re.compile(r"\bINSERT\s+INTO\b", re.I)

# BDD-07 — an assertion that a geodesic measure is a road measure.
ROAD_CLAIM = re.compile(
    r"(actual|real|true|road|driving|route)[\s_-]{0,3}"
    r"(trip[\s_-]?)?(distance|speed|km|route)"
    r"|(distance|speed)[\s_-]{0,3}(travell?ed|driven|on[\s_-]road)",
    re.I,
)
# Terms that mark text as *discussing* the geodesic/road distinction rather than asserting a
# road measure. A column alias never contains "geodesic" or "understates"; a caveat explaining
# why the column is not a road measure almost always does.
QUALIFIER = re.compile(
    r"\b(geodesic|haversine|straight[\s_-]?line|understate\w*|overstate\w*|caveat|"
    r"labell?ed|as[\s_-]such|approximat\w*)\b", re.I)

# Prose that *states* the rule contains a negation. Flagging it would flag the rule itself —
# the same class of bug as a secret-scanner matching its own pattern.
NEGATION = re.compile(
    r"\b(no|not|never|isn'?t|aren'?t|must[\s_-]not|cannot|can'?t|rather than|instead of|"
    r"avoid|forbid|don'?t|do[\s_-]not|claims?|assert\w*|described as|label it|NOT)\b", re.I)

SKIP_DIRS = {".git", "__pycache__", ".ruff_cache", ".venv", "node_modules", "target", "dbt_packages"}


def rel_to(path, root):
    """Repo-relative path where possible; absolute otherwise (--path may point outside the repo)."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def layer_of(path_str, text):
    p = path_str.lower()
    for layer in ("bronze", "silver", "gold"):
        if f"/{layer}" in p or f"{layer}_" in p or f"_{layer}" in p:
            return layer
    m = re.search(r"\b(bronze|silver|gold)_\w+", text or "", re.I)
    return m.group(1).lower() if m else None


def strip_sql_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"--.*$", "", ln) for ln in text.split("\n"))


SELF = "check_layer_contracts.py"


def scan_file(path, rel):
    if path.name == SELF:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    layer = layer_of(rel, text)
    code = strip_sql_comments(text) if path.suffix == ".sql" else text

    if layer == "silver":
        for pat, label in NONDETERMINISTIC:
            for i, line in enumerate(code.split("\n"), 1):
                if pat.search(line):
                    findings.append((rel, i, "silver-nondeterministic",
                                     f"{label} in a Silver transformation. Silver must be "
                                     f"deterministic — same Bronze in, identical Silver out."))
        for stmt in re.split(r";", code):
            if HAS_LIMIT.search(stmt) and not HAS_ORDER_BY.search(stmt):
                findings.append((rel, 0, "silver-nondeterministic",
                                 "LIMIT without ORDER BY returns an arbitrary subset."))
                break

    if layer == "bronze":
        for i, line in enumerate(code.split("\n"), 1):
            if BRONZE_MUTATION.search(line):
                findings.append((rel, i, "bronze-immutable",
                                 "Bronze is append-only. A correction is a new ingestion, "
                                 "never an edit to a landed row."))

    if layer == "gold":
        for i, line in enumerate(code.split("\n"), 1):
            if GOLD_APPEND.search(line):
                findings.append((rel, i, "gold-idempotent",
                                 "INSERT INTO a Gold mart double-counts on rerun. Replace the "
                                 "partition (BDD-04)."))

    # BDD-07 applies everywhere, not just in a layer.
    #
    # Negation is checked across a small window, not one line. Wrapped prose and YAML folded
    # scalars routinely split "must never be labelled as / actual route distance" across a line
    # break, and a single-line check would flag the sentence that states the rule. Documents
    # describing a prohibition must not trip the guard that enforces it.
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        # Underscores are separators here: an identifier such as
        # test_no_column_claims_road_distance states the prohibition, and without this the
        # guard flags the very test that enforces it.
        window = " ".join(lines[max(0, i - 3):i + 1]).replace("_", " ")
        if (ROAD_CLAIM.search(line)
                and not NEGATION.search(window) and not QUALIFIER.search(window)):
            findings.append((rel, i, "bdd-07-wording",
                             "coordinate-derived distance/speed described as actual road "
                             "distance or real driving speed. It is geodesic (Haversine) — "
                             f"label it 'estimated'.\n           > {line.strip()[:100]}"))
    return findings


def main():
    ap = argparse.ArgumentParser(description="Check Bronze/Silver/Gold layer contracts.")
    ap.add_argument("--path", action="append", help="directory or file to scan (repeatable)")
    ap.add_argument("--staged", action="store_true", help="scan only staged files")
    ap.add_argument("--quiet", action="store_true", help="only print on violation")
    args = ap.parse_args()

    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    root = Path(root.stdout.strip()) if root.returncode == 0 else Path.cwd()

    targets = []
    if args.staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                           cwd=root, capture_output=True, text=True)
        for rel in r.stdout.split("\n"):
            rel = rel.strip()
            if rel and (root / rel).is_file() and Path(rel).suffix in CODE_SUFFIXES | {".yml", ".yaml"}:
                targets.append((root / rel, rel))
    else:
        roots = [root / p for p in (args.path or SCAN_DIRS)]
        for base in roots:
            if base.is_file():
                targets.append((base, rel_to(base, root)))
            elif base.is_dir():
                for f in base.rglob("*"):
                    if (f.is_file() and f.suffix in CODE_SUFFIXES | {".yml", ".yaml"}
                            and not any(d in f.parts for d in SKIP_DIRS)):
                        targets.append((f, rel_to(f, root)))

    findings = []
    for path, rel in sorted(set(targets)):
        findings.extend(scan_file(path, rel))

    if findings:
        print("BLOCKED  layer contract violations:", file=sys.stderr)
        for rel, line, kind, msg in findings:
            loc = f"{rel}:{line}" if line else rel
            print(f"         [{kind}] {loc}\n           {msg}", file=sys.stderr)
        print("\nSee .claude/skills/medallion-transform/SKILL.md.", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK — {len(targets)} file(s) scanned, no layer contract violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
