#!/usr/bin/env python3
"""
run.py — run the dbt build with thresholds injected from the configs.

The single source of truth for every threshold and DQ parameter is configs/*.yml. This reads
them, converts approved values into dbt vars, and refuses to invent one: a value still marked
TBD_PENDING_PROFILING is passed through as the sentinel so the models can see it is unset and
withhold the KPIs that depend on it, rather than quietly substituting a default.

The default run is BLOCKED while a build-blocking KPI has no approved threshold — that is
BDD-05, and it is meant to be felt. Developing the other 18 KPIs is a deliberate opt-in via
--allow-withheld, which states in the output exactly what is being skipped.

    python -m src.transformations.run --target local
    python -m src.transformations.run --target databricks --allow-withheld
"""

import argparse
import inspect
import subprocess
import sys
from pathlib import Path

import yaml

def _repo_root() -> Path:
    """Repo root, whether run as a script or by a Databricks serverless task.

    A serverless `spark_python_task` exec's the compiled file instead of importing it, so
    `__file__` is undefined and a plain Path(__file__) raises NameError before main() is ever
    reached. The compiled code object still carries the path, which locates the root the same
    way in both environments.
    """
    path = globals().get("__file__") or inspect.currentframe().f_code.co_filename
    return Path(path).resolve().parents[2]


ROOT = _repo_root()
SENTINEL = "TBD_PENDING_PROFILING"


def load_vars():
    """Approved thresholds and DQ parameters as dbt vars; sentinels preserved verbatim."""
    kpi = yaml.safe_load((ROOT / "configs" / "kpi_config.yml").read_text())
    dq = yaml.safe_load((ROOT / "configs" / "quality_rules.yml").read_text())

    v, pending = {}, []
    for name, value in (kpi.get("thresholds") or {}).items():
        v[name] = value
        if value == SENTINEL:
            pending.append(name)

    for rule in dq.get("rules") or []:
        p = rule.get("parameter")
        if p and "value" in rule:
            v[p] = rule["value"]
            if rule["value"] == SENTINEL and p not in pending:
                pending.append(p)

    blocked = [(k["id"], k.get("threshold_ref")) for k in kpi.get("kpis", [])
               if k.get("blocks_build") and v.get(k.get("threshold_ref")) == SENTINEL]
    return v, pending, blocked


def _boolish(value) -> bool:
    """Parse the --allow-withheld value.

    A Databricks job parameter can only carry a string, so the flag has to accept one. An
    unrecognised value is an error rather than a silent False: a typo must not quietly re-arm
    a gate the operator meant to open, nor quietly open one they meant to keep shut.
    """
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0", ""):
        return False
    raise SystemExit(f"--allow-withheld: expected true or false, got {value!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the pipeline with config-driven thresholds.")
    ap.add_argument("--target", default="local", help="dbt target (local | databricks)")
    ap.add_argument("--command", default="build", help="dbt command: build | run | test")
    ap.add_argument("--select", default=None, help="dbt --select expression")
    ap.add_argument("--allow-withheld", nargs="?", const="true", default="false",
                    help="proceed with the unblocked KPIs while some thresholds are pending. "
                         "Takes an optional true/false so a Databricks job parameter can drive "
                         "it; bare --allow-withheld still means true.")
    ap.add_argument("--dry-run", action="store_true", help="print the dbt command and exit")
    a = ap.parse_args()

    v, pending, blocked = load_vars()

    if pending:
        print(f"Thresholds awaiting profiling ({len(pending)}): {', '.join(sorted(pending))}")
    if blocked:
        print("\nBuild-blocking KPIs (BDD-05):")
        for kid, ref in blocked:
            print(f"  {kid}  needs thresholds.{ref}")
        if not _boolish(a.allow_withheld):
            print("\nBLOCKED — these KPIs cannot be computed without an approved threshold, and a\n"
                  "plausible default is exactly what the gate exists to prevent. Either:\n"
                  "  1. run the profiling spec and approve the thresholds "
                  "(see the threshold-decision skill), or\n"
                  "  2. re-run with --allow-withheld to build the other KPIs and leave these out.",
                  file=sys.stderr)
            return 1
        print("\n--allow-withheld: building the remaining KPIs. The columns above are omitted\n"
              "from gold.trip_performance and marked withheld_pending_<threshold>.\n")

    cmd = ["dbt", a.command, "--target", a.target,
           "--project-dir", str(ROOT / "src" / "transformations"),
           "--vars", yaml.safe_dump(v, default_flow_style=True).strip()]
    if a.select:
        cmd += ["--select", a.select]

    print("$ " + " ".join(f"'{c}'" if " " in c else c for c in cmd) + "\n")
    if a.dry_run:
        return 0
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    # Exit non-zero only on failure. A Databricks serverless task runs this file inside an
    # IPython kernel, which reports any SystemExit — including SystemExit(0) — as a failed
    # task. Returning normally on success keeps the exit codes identical on a terminal while
    # letting the task succeed. A non-zero code still raises, which is what fails the gate.
    _rc = main()
    if _rc:
        sys.exit(_rc)
