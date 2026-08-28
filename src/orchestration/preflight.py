#!/usr/bin/env python3
"""
preflight.py — check a Databricks workspace is ready before running the pipeline.

Turns "did I set this up right?" into one command. Every check reports what is wrong and the
exact fix, so a failed connection does not become an afternoon of guessing.

Secrets are never printed. Values are shown masked (first 4 characters) purely so you can tell
which credential is loaded, and the script neither writes nor transmits them anywhere.

    cp .env.example .env      # fill in locally; .env is gitignored and hook-blocked
    python -m src.orchestration.preflight

Exit codes: 0 = ready · 1 = something needs fixing · 2 = missing dependency
"""

import argparse
import os
import socket
import sys

REQUIRED = ["DATABRICKS_HOST", "DATABRICKS_HTTP_PATH"]
AUTH_OAUTH = ["DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET"]
AUTH_PAT = ["DATABRICKS_TOKEN"]
OPTIONAL = {"DATABRICKS_CATALOG": "nyc_taxi_dev", "DATABRICKS_SCHEMA_DEV": "silver"}

# One schema per medallion layer, matching resources/catalog.yml. The landing volume and
# the write probe both belong to Bronze — that is where ingestion lands.
LAYER_SCHEMAS = ("bronze", "silver", "gold", "profiling")
VOLUME_SCHEMA = "bronze"

OK, BAD, WARN = "  [ok]  ", "  [!!]  ", "  [--]  "


def mask(v):
    if not v:
        return "(unset)"
    return f"{v[:4]}…{len(v)} chars" if len(v) > 8 else "(set)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a Databricks workspace is ready.")
    ap.add_argument("--timeout", type=int, default=30,
                    help="seconds to wait for the warehouse (default 30). A sleeping "
                         "serverless warehouse can take ~30s to wake, so raise this rather "
                         "than concluding the credentials are wrong.")
    args = ap.parse_args()

    # Without this a bad host hangs on DNS/TCP for minutes. A preflight that hangs tells you
    # less than one that fails quickly with a checklist.
    socket.setdefaulttimeout(args.timeout)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # .env is optional; the vars may already be exported

    problems = []

    # ---- 1. environment -----------------------------------------------------
    print("1. Environment")
    for k in REQUIRED:
        v = os.environ.get(k)
        print(f"{OK if v else BAD}{k} = {mask(v) if k.endswith('SECRET') or k.endswith('TOKEN') else (v or '(unset)')}")
        if not v:
            problems.append(f"{k} is unset — copy .env.example to .env and fill it in")

    has_oauth = all(os.environ.get(k) for k in AUTH_OAUTH)
    has_pat = all(os.environ.get(k) for k in AUTH_PAT)
    if has_oauth:
        print(f"{OK}auth = OAuth service principal (preferred)")
        print(f"       DATABRICKS_CLIENT_ID = {os.environ['DATABRICKS_CLIENT_ID'][:8]}…")
    elif has_pat:
        print(f"{WARN}auth = personal access token")
        print("       A PAT carries your full workspace privilege into every automated action")
        print("       (SECURITY_CHECKLIST Pillar 5). Prefer a service principal where Free")
        print("       Edition supports one; if not, keep the expiry short and rotate it.")
    else:
        print(f"{BAD}auth = none")
        problems.append("set either DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET, "
                        "or DATABRICKS_TOKEN")

    catalog = os.environ.get("DATABRICKS_CATALOG", OPTIONAL["DATABRICKS_CATALOG"])
    schema = os.environ.get("DATABRICKS_SCHEMA_DEV", OPTIONAL["DATABRICKS_SCHEMA_DEV"])
    print(f"{OK}catalog.schema = {catalog}.{schema}")

    if problems:
        print("\nFix these before continuing:")
        for p in problems:
            print(f"  - {p}")
        return 1

    # ---- 2. connectivity ----------------------------------------------------
    print("\n2. Connection")
    try:
        from databricks import sql as dbsql
    except ImportError:
        print(f"{BAD}databricks-sql-connector not installed")
        print("       pip install -r requirements.txt")
        return 2

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")

    # Probe TCP reachability first. The connector runs its own retry loop with backoff, so an
    # unreachable host hangs for minutes before surfacing anything useful. A 443 probe answers
    # "can I even see this workspace?" in seconds, and separates a network problem from an
    # auth problem — which are fixed in completely different places.
    try:
        with socket.create_connection((host, 443), timeout=args.timeout):
            print(f"{OK}{host}:443 reachable")
    except Exception as e:
        print(f"{BAD}cannot reach {host}:443 — {type(e).__name__}")
        print("\n       This is a network or hostname problem, not a credentials problem:")
        print("       1. Is DATABRICKS_HOST the workspace URL without https:// or a trailing /?")
        print("          e.g. dbc-1234abcd-5678.cloud.databricks.com")
        print("       2. Are you behind a VPN or proxy that blocks the workspace domain?")
        print("       3. Is the workspace still active? Free Edition workspaces can be reclaimed.")
        return 1

    kwargs = {"server_hostname": host, "http_path": os.environ["DATABRICKS_HTTP_PATH"],
              # Bound the connector's own retry loop so a bad path fails fast.
              "_retry_stop_after_attempts_count": 2}
    if has_oauth:
        kwargs.update(credentials_provider=None,
                      client_id=os.environ["DATABRICKS_CLIENT_ID"],
                      client_secret=os.environ["DATABRICKS_CLIENT_SECRET"])
    else:
        kwargs.update(access_token=os.environ["DATABRICKS_TOKEN"])

    try:
        with dbsql.connect(**{k: v for k, v in kwargs.items() if v is not None}) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchall()
                print(f"{OK}SELECT 1 succeeded — warehouse is reachable and awake")

                # ---- 3. Unity Catalog objects -------------------------------
                print("\n3. Unity Catalog")

                cur.execute("SHOW CATALOGS")
                cats = {r[0] for r in cur.fetchall()}
                if catalog in cats:
                    print(f"{OK}catalog {catalog} exists")
                else:
                    print(f"{BAD}catalog {catalog} not found")
                    print(f"       CREATE CATALOG IF NOT EXISTS {catalog};")
                    problems.append("catalog missing")

                if catalog in cats:
                    cur.execute(f"SHOW SCHEMAS IN {catalog}")
                    schemas = {r[0] for r in cur.fetchall()}
                    for layer in LAYER_SCHEMAS:
                        if layer in schemas:
                            print(f"{OK}schema {catalog}.{layer} exists")
                        else:
                            print(f"{BAD}schema {catalog}.{layer} not found")
                            print(f"       CREATE SCHEMA IF NOT EXISTS {catalog}.{layer};")
                            problems.append(f"schema {layer} missing")

                    try:
                        cur.execute(f"SHOW VOLUMES IN {catalog}.{VOLUME_SCHEMA}")
                        vols = {r[1] if len(r) > 1 else r[0] for r in cur.fetchall()}
                        if "landing" in vols:
                            print(f"{OK}volume {catalog}.{VOLUME_SCHEMA}.landing exists")
                        else:
                            print(f"{WARN}volume 'landing' not found — needed for the source CSV")
                            print(f"       CREATE VOLUME IF NOT EXISTS "
                                  f"{catalog}.{VOLUME_SCHEMA}.landing;")
                    except Exception as e:
                        print(f"{WARN}could not list volumes ({type(e).__name__})")

                    # ---- 4. write permission --------------------------------
                    print("\n4. Write access")
                    probe = f"{catalog}.{VOLUME_SCHEMA}._preflight_probe"
                    try:
                        cur.execute(f"CREATE OR REPLACE TABLE {probe} AS SELECT 1 AS ok")
                        cur.execute(f"DROP TABLE IF EXISTS {probe}")
                        print(f"{OK}can create and drop tables in "
                              f"{catalog}.{VOLUME_SCHEMA}")
                    except Exception as e:
                        print(f"{BAD}cannot write to {catalog}.{VOLUME_SCHEMA}: "
                              f"{type(e).__name__}")
                        print("       Ingestion needs write access to the Bronze schema.")
                        problems.append("no write access")
    except Exception as e:
        detail = str(e)[:200] or "no detail"
        timed_out = isinstance(e, (socket.timeout, TimeoutError)) or "timed out" in detail.lower()
        print(f"{BAD}connection failed: {type(e).__name__}: {detail}")
        if timed_out:
            print(f"\n       Timed out after {args.timeout}s. If the warehouse was asleep, retry")
            print(f"       with --timeout 90 before assuming the settings are wrong.")
        print("\n       Check in this order — the first failure is usually the real one:")
        print("       1. Is DATABRICKS_HOST your workspace URL (no https://, no trailing /)?")
        print("       2. Is DATABRICKS_HTTP_PATH the SQL warehouse path")
        print("          (SQL Warehouses -> your warehouse -> Connection details)?")
        print("       3. Is the warehouse running? Serverless warehouses sleep when idle;")
        print("          the first query wakes one and can take ~30s.")
        print("       4. Has the token or client secret expired?")
        return 1

    # ---- summary ------------------------------------------------------------
    print()
    if problems:
        print(f"NOT READY — {len(problems)} item(s) above need fixing.")
        return 1

    print("READY. Next:")
    print(f"  python -m src.ingestion.load_bronze \\")
    print(f"      --input /Volumes/{catalog}/{VOLUME_SCHEMA}/landing/train.csv \\")
    print(f"      --catalog {catalog} --schema {VOLUME_SCHEMA}")
    print("  python -m src.transformations.run --target databricks --allow-withheld")
    print("\n(--allow-withheld builds 18 of 20 KPIs; KPI-016/017 stay withheld until their")
    print(" thresholds are approved from profiling evidence.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
