#!/usr/bin/env python3
"""
check_dq_rules.py — validate the data-quality rule contract, and report test coverage.

Two jobs with deliberately different strictness:

  Structural validation (always strict). Every rule needs an id, a name, a type and an action;
  a `reject` rule needs a quarantine_reason or the rejection is unauditable (DQ-015); a `flag`
  rule needs a flag_column or the flag has nowhere to live. These are checkable today, so a
  malformed rule is an error today.

  Test coverage (advisory unless --strict). No tests exist yet because no pipeline exists.
  Failing on that would make this unusable, so coverage is reported and only enforced when
  asked — which is what you want once tests/data_quality/ is populated.

Usage:
    check_dq_rules.py                  # validate structure, report coverage
    check_dq_rules.py --strict         # also fail on uncovered rules
    check_dq_rules.py --rule DQ-007    # show one rule's implementation contract

Exit codes: 0 = valid · 1 = violation · 2 = usage/environment error
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check_dq_rules: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

DQ_CONFIG = "configs/quality_rules.yml"
TEST_DIR = "tests/data_quality"
CONTRACT = "docs/business/kpi-data-contract.md"

VALID_ACTIONS = {"reject", "flag", "policy"}
VALID_TYPES = {
    "completeness", "uniqueness", "validity", "consistency",
    "geographic", "derived_validity", "policy",
}


def main():
    ap = argparse.ArgumentParser(description="Validate DQ rules and report test coverage.")
    ap.add_argument("--strict", action="store_true", help="fail when a rule has no test")
    ap.add_argument("--rule", help="show the implementation contract for one rule id")
    ap.add_argument("--quiet", action="store_true", help="only print on failure")
    args = ap.parse_args()

    path = Path(DQ_CONFIG)
    if not path.exists():
        print(f"check_dq_rules: {DQ_CONFIG} not found", file=sys.stderr)
        return 2
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"BLOCKED  {DQ_CONFIG} is not valid YAML: {e}", file=sys.stderr)
        return 1

    rules = doc.get("rules") or []
    errors, warnings = [], []

    seen = set()
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            errors.append(f"rule #{i} is not a mapping")
            continue
        rid = r.get("id", f"<rule #{i}>")

        if rid in seen:
            errors.append(f"{rid} is defined more than once")
        seen.add(rid)

        for field in ("id", "name", "type", "action"):
            if not r.get(field):
                errors.append(f"{rid} is missing required field '{field}'")

        action, rtype = r.get("action"), r.get("type")
        if action and action not in VALID_ACTIONS:
            errors.append(f"{rid} action '{action}' is not one of {sorted(VALID_ACTIONS)}")
        if rtype and rtype not in VALID_TYPES:
            warnings.append(f"{rid} type '{rtype}' is not a known category")

        # DQ-015: a rejection nobody can audit is silent data loss.
        if action == "reject" and not r.get("quarantine_reason"):
            errors.append(f"{rid} rejects rows but has no quarantine_reason — every rejected "
                          f"record must be auditable (DQ-015).")
        # A flag with no column is a flag that goes nowhere.
        if action == "flag" and not r.get("flag_column"):
            errors.append(f"{rid} flags rows but has no flag_column.")
        # A policy is a behaviour, so it must say what it enforces.
        if action == "policy" and not r.get("enforces"):
            errors.append(f"{rid} is a policy but does not state what it enforces.")
        # Predicates belong to row-level rules only.
        if action in {"reject", "flag"} and not r.get("predicate"):
            errors.append(f"{rid} is a row-level rule with no predicate.")
        # A parameterised rule must name its parameter.
        if r.get("value") is not None and not r.get("parameter"):
            warnings.append(f"{rid} has a value but no parameter name")

    # Every rule id should resolve to the upstream contract.
    contract_path = Path(CONTRACT)
    if contract_path.exists():
        contract = contract_path.read_text(encoding="utf-8")
        orphans = [r.get("id") for r in rules
                   if isinstance(r, dict) and r.get("id") and r["id"] not in contract]
        if orphans:
            errors.append(f"rule id(s) not found in {CONTRACT}: {', '.join(orphans)}")

    # ---- single-rule view -------------------------------------------------------
    if args.rule:
        match = next((r for r in rules if isinstance(r, dict) and r.get("id") == args.rule), None)
        if not match:
            print(f"check_dq_rules: no rule {args.rule}", file=sys.stderr)
            return 2
        print(f"{match['id']} — {match.get('name')}")
        print(f"  type       {match.get('type')}")
        print(f"  action     {match.get('action')}"
              f"{'  (row leaves the valid population)' if match.get('action')=='reject' else ''}"
              f"{'  (row STAYS in the valid population)' if match.get('action')=='flag' else ''}")
        print(f"  severity   {match.get('severity')}")
        if match.get("predicate"):
            print(f"  predicate  {match['predicate']}")
        if match.get("quarantine_reason"):
            print(f"  quarantine {match['quarantine_reason']}")
        if match.get("flag_column"):
            print(f"  flag col   {match['flag_column']}")
        if match.get("value") == "TBD_PENDING_PROFILING":
            print(f"  BLOCKED    parameter '{match.get('parameter')}' awaits profiling — "
                  f"use the threshold-decision skill, do not invent a value.")
        if match.get("note"):
            print(f"  note       {' '.join(str(match['note']).split())}")
        return 0

    # ---- coverage ---------------------------------------------------------------
    covered, uncovered = [], []
    tdir = Path(TEST_DIR)
    test_text = ""
    if tdir.exists():
        for f in tdir.rglob("*.py"):
            test_text += f.read_text(encoding="utf-8", errors="ignore")
    for r in rules:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        (covered if r["id"] in test_text else uncovered).append(r["id"])

    if errors:
        print(f"BLOCKED  {DQ_CONFIG}:", file=sys.stderr)
        for e in errors:
            print(f"         - {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK — {len(rules)} rules, structurally valid.")
        by_action = {}
        for r in rules:
            by_action.setdefault(r.get("action"), []).append(r["id"])
        for a in ("reject", "flag", "policy"):
            if by_action.get(a):
                print(f"     {a:7} {len(by_action[a]):2}  {', '.join(by_action[a])}")
        pending = [r["id"] for r in rules if r.get("value") == "TBD_PENDING_PROFILING"]
        if pending:
            print(f"     awaiting profiling: {', '.join(pending)}")
        print(f"     test coverage: {len(covered)}/{len(rules)}"
              + (f" — no test references: {', '.join(uncovered)}" if uncovered else ""))
        for w in warnings:
            print(f"     · {w}")

    if args.strict and uncovered:
        print(f"\nBLOCKED  {len(uncovered)} rule(s) have no test in {TEST_DIR}: "
              f"{', '.join(uncovered)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
