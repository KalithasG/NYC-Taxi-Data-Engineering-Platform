#!/usr/bin/env python3
"""
validate_bundle.py — structural checks on the Databricks Asset Bundle.

`databricks bundle validate` needs a reachable workspace. This checks everything that does not:
YAML parses, every ${var.*} resolves to a declared variable, every ${resources.*} reference
points at a real resource, and every task entry-point file exists on disk.

A bundle that references a script someone deleted deploys fine and fails at run time, in a
workspace, where the feedback loop is slowest. That is the failure this catches early.

Exit codes: 0 = structurally sound · 1 = problem found
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _check_path(problems, job_name, task_key, base, rel):
    """Resolve a task path the way the Databricks CLI does: relative to the declaring file.

    Resolving against the bundle root instead accepts a path the CLI then rejects with
    `GetFileAttributesEx ...: The system cannot find the path specified` at deploy time —
    which is a slower and much less obvious way to learn the same thing.
    """
    target = (base / rel).resolve()
    if not target.exists():
        try:
            shown = target.relative_to(ROOT)
        except ValueError:
            shown = target
        problems.append(f"{job_name}.{task_key}: missing {shown} "
                        f"('{rel}' resolved against {base.name}/)")


def main() -> int:
    bundle_path = ROOT / "databricks.yml"
    if not bundle_path.exists():
        print("validate_bundle: databricks.yml not found", file=sys.stderr)
        return 1

    bundle = yaml.safe_load(bundle_path.read_text())
    files = [bundle_path, *sorted((ROOT / "resources").glob("*.yml"))]

    resources = {}
    # Where each resource was declared. The CLI resolves a task's relative paths against the
    # directory of the file that declares them, not against the bundle root, so checking them
    # needs the declaring file — see the `../src/...` prefixes in resources/jobs.yml.
    declared_in = {}
    for f in files[1:]:
        for kind, items in (yaml.safe_load(f.read_text()).get("resources") or {}).items():
            resources.setdefault(kind, {}).update(items)
            for item_name in items:
                declared_in[(kind, item_name)] = f.parent

    text = "".join(f.read_text() for f in files)
    problems = []

    declared = set(bundle.get("variables") or {})
    used = set(re.findall(r"\$\{var\.([a-z_]+)\}", text))
    for v in sorted(used - declared):
        problems.append(f"${{var.{v}}} is used but not declared in databricks.yml")

    for kind, name in re.findall(r"\$\{resources\.(\w+)\.(\w+)\.\w+\}", text):
        if name not in resources.get(kind, {}):
            problems.append(f"dangling reference: resources.{kind}.{name}")

    targets = bundle.get("targets") or {}
    if not targets:
        problems.append("no targets defined")
    if sum(1 for t in targets.values() if t.get("default")) != 1:
        problems.append("exactly one target must be marked default")

    for job_name, job in (resources.get("jobs") or {}).items():
        base = declared_in.get(("jobs", job_name), ROOT)
        seen = set()
        for task in job.get("tasks", []):
            key = task.get("task_key")
            seen.add(key)
            for dep in task.get("depends_on", []) or []:
                if dep["task_key"] not in seen:
                    problems.append(
                        f"{job_name}.{key} depends on '{dep['task_key']}', which is not "
                        f"defined before it")
            spt = task.get("spark_python_task") or {}
            if spt.get("python_file"):
                _check_path(problems, job_name, key, base, spt["python_file"])
            dbt = task.get("dbt_task") or {}
            if dbt.get("project_directory"):
                _check_path(problems, job_name, key, base,
                            dbt["project_directory"] + "/dbt_project.yml")

    if problems:
        print("BLOCKED  bundle structure:", file=sys.stderr)
        for p in problems:
            print(f"         - {p}", file=sys.stderr)
        return 1

    print(f"OK — bundle '{bundle['bundle']['name']}' is structurally sound.")
    print(f"     targets:   {', '.join(targets)}")
    for kind in sorted(resources):
        print(f"     {kind + ':':11}{', '.join(sorted(resources[kind]))}")
    print("\n     Not checked here: `databricks bundle validate` and deploy both need a "
          "reachable workspace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
