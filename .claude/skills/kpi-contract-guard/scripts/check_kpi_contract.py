#!/usr/bin/env python3
"""
check_kpi_contract.py — block KPI definition changes that lack a contract version bump.

A KPI whose formula, filter, grain or dimensions changes silently is the worst failure mode
this platform has: every dashboard keeps rendering, every test keeps passing, and the numbers
quietly stop meaning what they used to. KPI contract §20 therefore requires a version bump and
a seven-field changelog entry for any such change. This script makes that mechanical.

Usage:
    check_kpi_contract.py                 # compare HEAD against the working tree
    check_kpi_contract.py --staged        # compare HEAD against the index (pre-commit)
    check_kpi_contract.py --base <ref>    # compare against another ref

Exit codes: 0 = clean or properly versioned · 1 = violation · 2 = usage/environment error
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check_kpi_contract: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

CONFIG = "configs/kpi_config.yml"
CHANGELOG = "docs/business/kpi-changelog.md"

# Changing any of these changes what the KPI MEANS. Requires a version bump.
SEMANTIC_FIELDS = ("name", "formula", "filter", "grain", "dimensions", "mart", "threshold_ref")

# Changing these is editorial. Reported for visibility, never blocking — a gate that fires on
# every edit is a gate that gets switched off.
INFORMATIONAL_FIELDS = (
    "priority", "note", "caveat", "interpretation_caveat", "candidate_methods",
    "implementation_note", "acceptance", "output_units", "output_columns",
    "presentation_label", "companion_metrics", "components", "relationship",
    "tie_handling", "route_key", "primary_key", "threshold_status", "blocks_build",
)

# Ids that appeared in the v1.0 contract document but measure a model rather than the taxi
# operation. Out of scope for this platform — see kpi-data-contract.md §12 and spec §2.
OUT_OF_SCOPE_KPI_IDS = {"KPI-021", "KPI-022", "KPI-023", "KPI-024"}

# The seven fields KPI contract §20 requires for every change.
REQUIRED_CHANGELOG_FIELDS = (
    "old", "new", "reason", "effective", "impact", "migration", "approved by",
)


def git_show(ref_path, cwd):
    """Return file content at a git ref, or None when the path does not exist there."""
    # encoding is explicit: without it Python decodes git's bytes with the locale codec
    # (cp1252 on Windows) while the working tree is read as UTF-8, so every field containing
    # a non-ASCII character looks changed and the guard reports edits nobody made.
    r = subprocess.run(["git", "show", ref_path], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def load(text, label, errors):
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        errors.append(f"{label} is not valid YAML: {e}")
        return None


def kpis_by_id(doc):
    return {k.get("id"): k for k in (doc.get("kpis") or []) if isinstance(k, dict)}


def norm(v):
    """Normalize for comparison so list reordering is not a false positive."""
    return sorted(map(str, v)) if isinstance(v, list) else v


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


def changelog_entry_for(text, version, kpi_id):
    """
    Find the section for `version` and return its text if it mentions `kpi_id`.

    Deliberately forgiving about layout — the point is that a human wrote a real record,
    not that they matched a byte-exact template.
    """
    if not text:
        return None
    text = strip_code_fences(text)
    # Split on version headings like "## v1.1" / "## 1.1 — 2026-09-03"
    blocks = re.split(r"^##\s+v?(\d+\.\d+)", text, flags=re.MULTILINE)
    for i in range(1, len(blocks) - 1, 2):
        if blocks[i].strip() == str(version).strip():
            body = blocks[i + 1]
            if kpi_id in body:
                return body
    return None


def missing_fields(entry_text):
    low = entry_text.lower()
    return [f for f in REQUIRED_CHANGELOG_FIELDS if f not in low]


def main():
    ap = argparse.ArgumentParser(description="Guard KPI definitions against unversioned change.")
    ap.add_argument("--staged", action="store_true",
                    help="compare against the git index (use in pre-commit)")
    ap.add_argument("--base", default="HEAD", help="base ref to compare against (default HEAD)")
    ap.add_argument("--quiet", action="store_true", help="only print on violation")
    args = ap.parse_args()

    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True)
    if root.returncode != 0:
        print("check_kpi_contract: not inside a git repository", file=sys.stderr)
        return 2
    root = Path(root.stdout.strip())

    errors, notes, informational = [], [], []

    base_text = git_show(f"{args.base}:{CONFIG}", root)
    if base_text is None:
        if not args.quiet:
            print(f"check_kpi_contract: {CONFIG} not present at {args.base} — nothing to compare.")
        return 0

    if args.staged:
        head_text = git_show(f":{CONFIG}", root)
        if head_text is None:
            if not args.quiet:
                print(f"check_kpi_contract: {CONFIG} not staged — skipping.")
            return 0
    else:
        p = root / CONFIG
        if not p.exists():
            errors.append(f"{CONFIG} is missing from the working tree.")
            head_text = None
        else:
            head_text = p.read_text(encoding="utf-8")

    base = load(base_text, f"{CONFIG}@{args.base}", errors)
    curr = load(head_text, CONFIG, errors)
    if errors or base is None or curr is None:
        for e in errors:
            print(f"BLOCKED  {e}", file=sys.stderr)
        return 1 if errors else 0

    base_k, curr_k = kpis_by_id(base), kpis_by_id(curr)
    changed_ids = set()

    # --- semantic field changes -------------------------------------------------
    for kid in sorted(set(base_k) & set(curr_k)):
        for f in SEMANTIC_FIELDS:
            b, c = norm(base_k[kid].get(f)), norm(curr_k[kid].get(f))
            if b != c:
                changed_ids.add(kid)
                notes.append(f"{kid}.{f} changed:\n      old: {b!r}\n      new: {c!r}")
        for f in INFORMATIONAL_FIELDS:
            if norm(base_k[kid].get(f)) != norm(curr_k[kid].get(f)):
                informational.append(f"{kid}.{f} changed (editorial — not blocking)")

    # --- KPIs added or removed --------------------------------------------------
    for kid in sorted(set(curr_k) - set(base_k)):
        changed_ids.add(kid)
        notes.append(f"{kid} ADDED to the contract")
    for kid in sorted(set(base_k) - set(curr_k)):
        changed_ids.add(kid)
        notes.append(f"{kid} REMOVED from the contract")

    # --- scope violation: model metrics are not this platform's job -------------
    reintroduced = sorted(OUT_OF_SCOPE_KPI_IDS & set(curr_k))
    if reintroduced:
        errors.append(
            f"{', '.join(reintroduced)}: model performance metrics, out of scope for this "
            f"platform (kpi-data-contract.md §12, spec §2) — they measure a model, not the "
            f"taxi operation. "
            f"Adding them here would make what this platform measures ambiguous."
        )

    # --- contract-level defaults ------------------------------------------------
    for key in ("default_filter", "default_grain", "time_of_day_buckets"):
        if norm(base.get(key)) != norm(curr.get(key)):
            changed_ids.add(f"<contract.{key}>")
            notes.append(f"contract-level {key} changed — affects every KPI that inherits it:\n"
                         f"      old: {norm(base.get(key))!r}\n      new: {norm(curr.get(key))!r}")

    # --- declared count must match reality --------------------------------------
    declared, actual = curr.get("kpi_count"), len(curr_k)
    if declared != actual:
        errors.append(f"kpi_count says {declared} but {actual} KPIs are defined. "
                      f"The declared count is a cross-check — keep it in sync.")

    # --- version bump + changelog entry -----------------------------------------
    base_ver, curr_ver = str(base.get("contract_version")), str(curr.get("contract_version"))
    real_changes = sorted(changed_ids)

    if real_changes:
        if base_ver == curr_ver:
            errors.append(
                f"{len(real_changes)} KPI definition change(s) with contract_version still "
                f"{curr_ver}. KPI contract §20 requires a version bump: 1.1+ for a clarification "
                f"that does not alter meaning, 2.0+ for a formula, population, grain, threshold "
                f"or dimension change that affects interpretation or historical comparability."
            )
        else:
            cl_path = root / CHANGELOG
            cl_text = cl_path.read_text(encoding="utf-8") if cl_path.exists() else None
            if cl_text is None:
                errors.append(f"contract_version bumped {base_ver} -> {curr_ver} but {CHANGELOG} "
                              f"does not exist. Every change needs a recorded entry.")
            else:
                for kid in real_changes:
                    entry = changelog_entry_for(cl_text, curr_ver, kid)
                    if entry is None:
                        errors.append(f"No {CHANGELOG} entry under v{curr_ver} mentioning {kid}.")
                    else:
                        miss = missing_fields(entry)
                        if miss:
                            errors.append(f"{CHANGELOG} entry for {kid} under v{curr_ver} is "
                                          f"missing required field(s): {', '.join(miss)}.")

    # --- report -----------------------------------------------------------------
    if notes and not args.quiet:
        print("KPI definition changes detected:")
        for n in notes:
            print(f"  - {n}")
    if informational and not args.quiet:
        for n in informational:
            print(f"  · {n}")

    if errors:
        print()
        for e in errors:
            print(f"BLOCKED  {e}", file=sys.stderr)
        print("\nSee .claude/skills/kpi-contract-guard/SKILL.md for how to make this change "
              "properly.", file=sys.stderr)
        return 1

    if not args.quiet:
        if real_changes:
            print(f"\nOK — contract_version {base_ver} -> {curr_ver} with complete "
                  f"{CHANGELOG} entries.")
        else:
            print("OK — no KPI definition changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
