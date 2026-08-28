# Running the Pipeline — Databricks Free Edition

Two ways to run the same models: **locally** through a Spark session (no workspace, no
credentials — this is how the pipeline was verified) and on **Databricks Free Edition**.

---

## 1. Local verification — start here

Free Edition is serverless-only and metered, so getting the models right locally first is both
cheaper and faster. Local Spark is the same SQL engine Databricks runs, so the dialect matches.

**Prerequisites:** Python 3.11 (matching Databricks serverless) and a **JDK 17 or 21** with
`JAVA_HOME` set — PySpark is a JVM program, and a missing JDK fails as a Py4J gateway error that
does not mention Java.

### macOS / Linux / WSL

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SPARK_CONF_DIR="$PWD/conf"     # Delta locally — same format as Databricks

# Synthetic fixture with known planted defects — NOT the Kaggle data
python tests/fixtures/make_fixture.py --out data/fixture_trips.csv

mkdir -p ~/.dbt && cp src/transformations/profiles.yml.example ~/.dbt/profiles.yml

python -m src.ingestion.load_bronze --input data/fixture_trips.csv --local
python -m src.transformations.run --target local --allow-withheld
pytest tests/test_pipeline_e2e.py
```

### Windows

**WSL2 is the shortcut.** `wsl --install` in an admin PowerShell, reboot, then run the block
above verbatim inside the Linux shell. It avoids the whole Hadoop-on-Windows problem below, and
it is the same OS Databricks runs, so what passes locally is what runs there.

Native PowerShell works too, with two extra setup steps and different syntax:

```powershell
# Windows PowerShell 5.1 has no `&&` — one statement per line. (PowerShell 7+ supports it.)
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # blocked? Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt

$env:SPARK_CONF_DIR = "$PWD\conf"   # `export` is bash; PowerShell uses $env:

New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.dbt" | Out-Null
Copy-Item src\transformations\profiles.yml.example "$env:USERPROFILE\.dbt\profiles.yml"

python tests\fixtures\make_fixture.py --out data\fixture_trips.csv
python -m src.ingestion.load_bronze --input data\fixture_trips.csv --local
python -m src.transformations.run --target local --allow-withheld
pytest tests\test_pipeline_e2e.py
```

**Hadoop native binaries.** Spark's local filesystem access on Windows goes through Hadoop's
native layer, which ships no Windows binaries. Without them the first write fails with
`HADOOP_HOME and hadoop.home.dir are unset` or
`UnsatisfiedLinkError: NativeIO$Windows.access0` — neither of which mentions the real cause.
Put a matching `winutils.exe` and `hadoop.dll` in `C:\hadoop\bin`, then:

```powershell
$env:HADOOP_HOME = "C:\hadoop"
$env:PATH = "$env:HADOOP_HOME\bin;$env:PATH"
```

They must match the Hadoop version PySpark bundles, not the newest available. Check it:

```powershell
Get-ChildItem .venv\Lib\site-packages\pyspark\jars\hadoop-client-api-*.jar | Select-Object Name
```

`$env:` assignments last only for the current PowerShell window. Set `JAVA_HOME`, `HADOOP_HOME`
and the `PATH` entry permanently under System Properties → Environment Variables, or re-set them
each session.

**Not verified on Windows.** The pipeline was built and tested on Linux; the PowerShell
translation above is mechanical and the Hadoop requirement is a known Spark-on-Windows
constraint, but neither has been executed here. WSL2 is the path that is actually verified.

### Either platform

Expect `Done. PASS=28` from dbt and `21 passed` from pytest.

**Why `--allow-withheld` is needed.** Without it the run stops: KPI-016 and KPI-017 depend on
thresholds that are still `TBD_PENDING_PROFILING`, and BDD-05 says a KPI must not be computed
from a guessed cutoff. The flag builds the other 18 and marks the two as withheld, naming the
threshold each is waiting on. Once profiling lands and the thresholds are approved, drop the
flag and all 20 build.

Local Bronze is **Delta**, same as Databricks. `conf/spark-defaults.conf` supplies the Delta
extensions to every local Spark session — ingestion, dbt, profiling and pytest — so one config
covers all four instead of four drifting copies. Verify with `DESCRIBE HISTORY bronze_trips`;
`tests/test_pipeline_e2e.py` asserts both the format and that the history contains no mutating
operation, because Bronze is append-only.

There is deliberately **no `MERGE` on Bronze**. MERGE updates rows in place, which is exactly
what the append-only contract forbids; idempotency comes from the `source_hash` check instead.

---

## 2. Databricks Free Edition

### Option A — deploy the Asset Bundle (recommended)

The catalog, four schemas, landing volume, job and grants are declared in `databricks.yml` and
`resources/`, so they deploy reproducibly instead of being clicked together in the UI:

```bash
pip install databricks-cli          # or: brew install databricks
databricks configure                # or rely on the .env you filled in
python scripts/validate_bundle.py   # structure check, no workspace needed
databricks bundle validate --target dev
databricks bundle deploy  --target dev
databricks bundle run nyc_taxi_pipeline --target dev
```

`dev` is the default target, so an accidental `bundle deploy` cannot touch prod. Before
deploying, replace the placeholder principals in `resources/permissions.yml` with real Unity
Catalog groups — they are left obviously fake rather than guessed.

**Not verified from here.** No Databricks host is reachable from the environment this repo was
built in, so `bundle validate` and `deploy` have never been executed. `scripts/validate_bundle.py`
checks everything that does not need a workspace: YAML parses, every `${var.*}` resolves, every
`${resources.*}` points at something real, and every task entry-point file exists.

### Option B — manual one-time setup

The names below are not arbitrary: they are what `databricks.yml` and `resources/` declare, and
what every task parameter resolves to. Creating a different layout by hand is the fastest way to
a job that deploys and then cannot find its own tables.

1. **Create the workspace** at the Databricks Free Edition sign-up. Serverless compute and Unity
   Catalog come enabled; there is no cluster to configure.
2. **Catalog, schemas and volume.** In a SQL editor — one schema per medallion layer, because
   that is what the grants in `resources/permissions.yml` attach to:
   ```sql
   CREATE CATALOG IF NOT EXISTS nyc_taxi_dev;
   CREATE SCHEMA  IF NOT EXISTS nyc_taxi_dev.bronze;
   CREATE SCHEMA  IF NOT EXISTS nyc_taxi_dev.silver;
   CREATE SCHEMA  IF NOT EXISTS nyc_taxi_dev.gold;
   CREATE SCHEMA  IF NOT EXISTS nyc_taxi_dev.profiling;
   CREATE VOLUME  IF NOT EXISTS nyc_taxi_dev.bronze.landing;
   ```
   `nyc_taxi_dev` is the **dev** catalog; the prod target uses `nyc_taxi` with the same four
   schemas. The landing volume lives in Bronze — that is the layer that ingests.
3. **Upload the dataset** to the volume (`data/README.md` covers acquisition and hashing):
   `/Volumes/nyc_taxi_dev/bronze/landing/train.csv`
4. **Credentials.** Copy `.env.example` to `.env` and fill it in. Prefer an OAuth service
   principal over a personal access token — a PAT carries your whole workspace privilege into
   every automated action, which is the confused-deputy risk in `SECURITY_CHECKLIST.md`
   Pillar 5. The pre-commit hook blocks both from being committed.
5. **Git folder.** Clone this repo into the workspace (Workspace → Repos → Add Repo) so the
   notebooks and the dbt project are versioned rather than pasted.

### Option C — browser only (phone, tablet, or any machine without a terminal)

Options A and B both assume a shell: A needs the `databricks` CLI, B needs local Python for
`preflight` and the run commands. On a phone there is neither. Everything below happens inside
the Databricks web UI, so the only local requirement is Chrome.

**Chrome setup.** Open the workspace URL, then ⋮ → **Desktop site**. The Databricks UI is a
desktop app and its mobile layout hides the notebook toolbar and the job task editor. Turn the
phone landscape; the SQL editor and notebook cells are usable, the Jobs task graph is cramped but
workable. A Bluetooth keyboard turns this from painful into merely slow. Sign-in with a passkey
is easier than typing a password into a desktop-mode form.

**1. Get the code in without a terminal.** Workspace → **Create** → **Git folder**, URL
`https://github.com/KalithasG/NYC-Taxi-Data-Engineering-Platform`, branch
`claude/project-prerequisite-files-lcs3px`. A private repo needs a GitHub PAT under Settings →
Linked accounts. This is what replaces `git clone`, and it keeps the notebooks versioned rather
than pasted.

**2. Create the objects.** SQL editor → paste the `CREATE CATALOG` / `CREATE SCHEMA` /
`CREATE VOLUME` block from Option B → Run. This is the one step where a typo costs you an hour
later, so run `SHOW SCHEMAS IN nyc_taxi_dev` afterwards and check you get four rows.

**3. Skip the Kaggle upload on the first pass.** `train.csv` is a ~190 MB download-then-upload
round trip through a phone, and a dropped browser upload leaves a truncated file that fails as a
*data* problem three steps later rather than an obvious transfer error. The repo generates a
441-row fixture with fifteen planted defect classes instead. In a notebook attached to serverless:

```python
import os, sys, subprocess
os.chdir("/Workspace/Users/<you>/NYC-Taxi-Data-Engineering-Platform")   # the Git folder root
subprocess.run([sys.executable, "tests/fixtures/make_fixture.py",
                "--out", "/Volumes/nyc_taxi_dev/bronze/landing/train.csv"], check=True)
```

Deliberately `subprocess` with the notebook's own interpreter rather than `%sh`: serverless
notebooks restrict shell access, and the fixture writes through a plain file handle, which the
`/Volumes` FUSE path accepts. `os.chdir` matters — a notebook's working directory is its own
folder, not the repo root, so the relative script path fails without it.

That proves the whole pipeline end to end from the phone. Do the real dataset from a computer
later — the only thing that changes is the file behind the same volume path.

**4. Get the warehouse id.** SQL Warehouses → your warehouse → **Connection details** → the
`/sql/1.0/warehouses/<id>` path. The id is the last segment. The dbt task needs it.

**5. Build the job.** Workflows → **Create job**, then add the four tasks in the order
`resources/jobs.yml` declares — `threshold_gate`, `ingest_bronze`, `build_silver_gold`,
`profile_source` — with the same type, entry point and parameters. Set the job parameters
`catalog=nyc_taxi_dev`, `landing_path=/Volumes/nyc_taxi_dev/bronze/landing/train.csv`,
`allow_withheld=true`. Source: **Git provider**, pointing at the same repo and branch.

Read the task fields out of `resources/jobs.yml` rather than from memory — it is the definition
Option A deploys, and hand-entering something different is how the two silently diverge.

**Expect `threshold_gate` to pass and the run to build 18 of 20 KPIs.** KPI-016 and KPI-017 stay
withheld until their thresholds are approved from profiling evidence; that is BDD-05 working, not
a failure. Setting `allow_withheld=false` makes the gate hard.

**What you cannot do from the phone.** `databricks bundle validate` / `deploy` (CLI only), the
local Spark verification in §1, `scripts/validate_bundle.py`, `preflight.py`, and pytest. The job
run is therefore the only signal you get — so if a task fails, read its task log in the run
detail rather than assuming the setup is wrong.

---

### Check the setup before running anything

```bash
cp .env.example .env        # fill in locally — .env is gitignored and blocked by the hook
python -m src.orchestration.preflight
```

Applies to Options A and B; Option C has no terminal to run it in.

This validates, in order: env vars present, workspace reachable on :443, warehouse answers
`SELECT 1`, the catalog and all four layer schemas exist, the `landing` volume exists in Bronze,
and Bronze is writable. Each failure prints
the exact fix. It never prints a secret — credentials are shown masked so you can tell which one
is loaded, and nothing is written or transmitted.

A serverless warehouse sleeps when idle and takes roughly 30s to wake, so a first-run timeout is
usually a sleeping warehouse rather than bad credentials — retry with `--timeout 90` before
changing anything.

### Run it

```bash
python -m src.ingestion.load_bronze \
  --input /Volumes/nyc_taxi_dev/bronze/landing/train.csv \
  --catalog nyc_taxi_dev --schema bronze

python -m src.transformations.run --target databricks --allow-withheld
```

`resources/jobs.yml` defines the same sequence as a Lakeflow Job, with the threshold gate as the
first task — a run that would compute a KPI from an unapproved threshold fails before it writes
anything.

### What lands

On Databricks, in catalog `nyc_taxi_dev`:

| Layer | Schema | Tables |
|---|---|---|
| Bronze | `bronze` | `bronze_trips` — append-only, `source_hash` tagged (+ the `landing` volume) |
| Silver | `silver` | `silver_trips`, `silver_trips_quarantine` (+ two views) |
| Gold | `gold` | `trip_performance`, `demand_metrics`, `geographic_metrics`, `vendor_performance`, `data_quality` |
| Profiling | `profiling` | the six `profile_*` tables |

The split is what `resources/permissions.yml` grants against — analysts get `SELECT` on `gold`
and nothing else, and an analyst who can read Silver can publish a number that never passed the
KPI contract.

**The local run is not laid out this way.** Locally only Gold is relocated (contract v1.2);
Bronze, Silver and the profiling tables share `nyc_taxi_dev`, because a single-process Spark
session has no grants for the split to serve. Table *names* are identical either way, so the
models and queries do not change — only the schema they resolve in.

Upgrading from a pre-v1.2 workspace: drop the superseded `gold_<mart>` tables after the first
rebuild. They are left behind, not renamed, and a dashboard still pointed at one keeps rendering
numbers that quietly stopped updating.

### Dashboard

Build the executive view (`kpi-discussion.md` §11) as an AI/BI Dashboard over the Gold marts.
One wording rule applies to every tile: `estimated_distance_km` and `estimated_speed_kmh` are
geodesic. Label them "estimated" — never "actual", "road" or "route" distance/speed. This is
BDD-07, and `check_layer_contracts.py` enforces it on the models.

---

## Known unknowns

These are recorded rather than assumed, and are worth confirming against your own workspace:

- **Lakeflow Declarative Pipelines** availability on Free Edition is unconfirmed (spec OQ-3).
  The pipeline deliberately does not depend on it — dbt is the transformation layer either way.
- **Serverless quota** versus a full-dataset run (spec OQ-4). Develop against the fixture or a
  sampled subset; run the full dataset once the models are settled.
- **Free Edition is non-commercial.** Fine for a portfolio project; not a production platform.
- **`dbt_task` availability on Free Edition** is unconfirmed. If Workflows will not offer a dbt
  task type, run the transformation from a notebook instead: `%pip install dbt-databricks`, then
  `src/transformations/run.py`, which needs a `profiles.yml` the dbt task would otherwise
  generate for you.
- **Nothing in §2 has been executed.** No Databricks host was reachable from the environment this
  repo was built in, so every Databricks-side step here is derived from the declarations in
  `databricks.yml` and `resources/`, not from a run. The local path in §1 is the part that is
  actually verified. Expect to correct a field or two on first contact, and fix it in
  `resources/jobs.yml` rather than only in the UI.
