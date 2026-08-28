#!/usr/bin/env python3
"""
check_thresholds.py — stop a TBD threshold from being filled in without evidence and approval.

Six thresholds in this project are deliberately unset. A threshold looks like a number but
behaves like an unreviewed policy decision: pick 3600 for "long trip" and you have silently
defined what the business considers abnormal, with no evidence and no approver. KPI contract §18
and profiling spec §31 require the number to come from profiling evidence and a human decision.

Two distinct jobs:

  default / --staged   Fail only when a threshold TRANSITIONS from TBD_PENDING_PROFILING to a
                       concrete value without a complete decision record. Pending TBDs are the
                       normal, correct state today — never fail merely because they exist, or
                       the hook becomes unusable and gets disabled.

  --gate               Fail while any build-blocking KPI still has an unresolved threshold.
                       This is the BDD-05 mechanism, for the pipeline to call at build time.

Exit codes: 0 = clean · 1 = violation · 2 = usage/environment error
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check_thresholds: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

KPI_CONFIG = "configs/kpi_config.yml"
DQ_CONFIG = "configs/quality_rules.yml"
DECISIONS = "docs/profiling/threshold-decisions.md"
SENTINEL = "TBD_PENDING_PROFILING"

# A complete decision record. Wording is matched loosely — the goal is that a human actually
# reasoned and signed, not that they reproduced a template character for character.
REQUIRED = {
    "value": ("value",),
    "method": ("method",),
    "evidence": ("evidence",),
    "records affected": ("records affected", "affected records", "records impacted"),
    "business rationale": ("rationale", "business rationale"),
    "alternatives considered": ("alternative", "alternatives"),
    "approved by": ("approved by", "approver"),
    "effective date": ("effective",),
    "contract bump": ("contract", "version bump"),
}

# An approver must be a person. These are not people.
PLACEHOLDER_APPROVERS = re.compile(
    r"(_pending_|<[^>]*>|tbd|todo|n/?a|none|pending|xxx|claude|gpt|ai\b|the agent|assistant)",
    re.IGNORECASE,
)


def git_show(ref_path, cwd):
    # encoding is explicit: without it Python decodes git's bytes with the locale codec
    # (cp1252 on Windows) while the working tree is read as UTF-8, so every field containing
    # a non-ASCII character looks changed and the guard reports edits nobody made.
    r = subprocess.run(["git", "show", ref_path], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def load(text):
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def collect(kpi_doc, dq_doc):
    """Map every threshold-bearing key to its current value."""
    out = {}
    for name, val in ((kpi_doc or {}).get("thresholds") or {}).items():
        out[f"thresholds.{name}"] = val
    for rule in (dq_doc or {}).get("rules") or []:
        if isinstance(rule, dict) and "value" in rule:
            out[f"{rule.get('id')}.{rule.get('parameter', 'value')}"] = rule["value"]
    return out


def strip_code_fences(text):
    """
    Remove fenced code blocks before parsing.

    Documentation in these files shows an example entry — the same headings and the same
    field names a real record uses. Without this, a template in the docs is indistinguishable
    from an approved record, and the gate passes on an example nobody wrote.
    """
    out, fenced = [], False
    for line in (text or "").split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def heading_level(line):
    """Number of leading '#' characters in a markdown heading."""
    return len(line) - len(line.lstrip("#"))


def record_for(text, key):
    """
    Return the decision-record block for a threshold key, or None.

    A record is anchored by the bare threshold name appearing in the document; the block runs
    to the next heading of the same or higher level.
    """
    if not text:
        return None
    bare = key.split(".")[-1]
    lines = strip_code_fences(text).split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#") and (bare in ln or key in ln):
            start = i
            break
    if start is None:
        return None
    level = heading_level(lines[start])
    body = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.lstrip().startswith("#") and heading_level(ln) <= level:
            break
        body.append(ln)
    return "\n".join(body)


def audit_record(block):
    """Return (missing_fields, approver_problem)."""
    low = block.lower()
    missing = [label for label, aliases in REQUIRED.items()
               if not any(a in low for a in aliases)]
    problem = None
    for ln in block.split("\n"):
        if "approved by" in ln.lower() or "approver" in ln.lower():
            after = ln.split(":", 1)[1] if ":" in ln else ""
            after = after.replace("*", "").replace("_", "").strip()
            if not after or PLACEHOLDER_APPROVERS.search(after):
                problem = f"approver is not a named person: {after or '(blank)'!r}"
            break
    return missing, problem


def main():
    ap = argparse.ArgumentParser(description="Guard TBD thresholds against evidence-free resolution.")
    ap.add_argument("--staged", action="store_true", help="compare against the git index (pre-commit)")
    ap.add_argument("--base", default="HEAD", help="base ref to compare against (default HEAD)")
    ap.add_argument("--gate", action="store_true",
                    help="fail while any build-blocking KPI has an unresolved threshold (BDD-05)")
    ap.add_argument("--quiet", action="store_true", help="only print on violation")
    args = ap.parse_args()

    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if root.returncode != 0:
        print("check_thresholds: not inside a git repository", file=sys.stderr)
        return 2
    root = Path(root.stdout.strip())

    def read_current(rel):
        if args.staged:
            t = git_show(f":{rel}", root)
            if t is not None:
                return t
        p = root / rel
        return p.read_text(encoding="utf-8") if p.exists() else None

    curr_kpi = load(read_current(KPI_CONFIG))
    curr_dq = load(read_current(DQ_CONFIG))
    if curr_kpi is None:
        print(f"check_thresholds: cannot read {KPI_CONFIG}", file=sys.stderr)
        return 2

    current = collect(curr_kpi, curr_dq)
    pending = [k for k, v in current.items() if v == SENTINEL]
    resolved_now = {k: v for k, v in current.items() if v != SENTINEL}

    # ---- --gate: build-time check (BDD-05) --------------------------------------
    if args.gate:
        blocking = [k for k in (curr_kpi.get("kpis") or [])
                    if isinstance(k, dict) and k.get("blocks_build")]
        unresolved = []
        for k in blocking:
            ref = k.get("threshold_ref")
            if ref and current.get(f"thresholds.{ref}") == SENTINEL:
                unresolved.append((k["id"], ref))
        if unresolved:
            for kid, ref in unresolved:
                print(f"BLOCKED  {kid} depends on thresholds.{ref}, still {SENTINEL}. "
                      f"No Gold row may be written for it.", file=sys.stderr)
            print("\nResolve via docs/profiling/threshold-decisions.md, or exclude these KPIs "
                  "from the build.", file=sys.stderr)
            return 1
        if not args.quiet:
            print("OK — every build-blocking KPI has an approved threshold.")
        return 0

    # ---- default/--staged: only newly-resolved thresholds need paperwork --------
    base_kpi = load(git_show(f"{args.base}:{KPI_CONFIG}", root))
    base_dq = load(git_show(f"{args.base}:{DQ_CONFIG}", root))
    baseline = collect(base_kpi, base_dq) if base_kpi else {}

    # A threshold needs a record when it was TBD at the base ref, or is entirely new.
    newly_set = {k: v for k, v in resolved_now.items()
                 if baseline.get(k, SENTINEL) == SENTINEL}

    if not newly_set:
        if not args.quiet:
            names = sorted({p.split('.')[-1] for p in pending})
            print(f"OK — no threshold newly resolved. {len(pending)} still awaiting profiling "
                  f"({len(names)} distinct): {', '.join(names) or 'none'}")
        return 0

    dec_path = root / DECISIONS
    dec_text = dec_path.read_text(encoding="utf-8") if dec_path.exists() else None

    errors = []
    for key, val in sorted(newly_set.items()):
        block = record_for(dec_text, key)
        if block is None:
            errors.append(
                f"{key} was set to {val!r} but {DECISIONS} has no decision record for it.\n"
                f"           A threshold without a record is invisible business logic — it looks "
                f"like a number and behaves like an unreviewed policy."
            )
            continue
        missing, approver = audit_record(block)
        if missing:
            errors.append(f"{key} record is missing: {', '.join(missing)}.")
        if approver:
            errors.append(f"{key} record {approver}. Approval is a human act — profiling spec §31 "
                          f"and the AI guardrails in kpi-discussion.md §15 are explicit that the agent "
                          f"may propose thresholds but never approve them.")

    if errors:
        for e in errors:
            print(f"BLOCKED  {e}", file=sys.stderr)
        print("\nSee .claude/skills/threshold-decision/SKILL.md for the evidence required.",
              file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK — {len(newly_set)} threshold(s) resolved with complete records: "
              f"{', '.join(sorted(newly_set))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
