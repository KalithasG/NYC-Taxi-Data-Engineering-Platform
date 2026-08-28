# Security Checklist — NYC Taxi Data Engineering Platform (7-Pillar Safety Envelope)

**Tier:** structured · **Stage 5** of the agentic-engineering workflow

> Assume the model can fail or be compromised — security lives outside it, in the harness.
> Legend: ✅ done · ▶ planned · — deferred (each deferral justified, never left blank).

## Threat model in one paragraph

The dataset is public Kaggle data: no PII, no money, no production traffic. That genuinely lowers
the stakes on most pillars. **One thing does not scale down: the Databricks credential.** A leaked
PAT grants workspace access — a real incident regardless of how benign the data is. So pillars 2
and 5 are treated at production depth while the rest are scaled to tier. The other live risk is
**silent business-logic corruption**: an agent changing a KPI formula or inventing a threshold does
no "security" damage but destroys the platform's entire value proposition. Pillar 7 covers it.

---

## Pillar 1 — Infrastructure & networking

- ✅ Agent code runs in an ephemeral, isolated remote container; reclaimed after the session.
- ✅ Databricks compute is **serverless** — no self-managed cluster to harden or leave running.
- ▶ Network egress: outbound traffic goes through the session's configured proxy. Databricks
  workspace URL is the only external data destination.
- — Custom kernel-level sandbox (gVisor): **deferred.** The execution environment already provides
  container isolation, and no untrusted third-party code executes in this pipeline.

## Pillar 2 — Data · *production depth, not tier depth*

- ✅ Source data is public and contains no PII. Coordinates are trip endpoints, not identities.
- ✅ Raw data is **gitignored** and blocked by the pre-commit hook — Kaggle licensing plus repo size.
- ▶ Unity Catalog grants scoped least-privilege: read `nyc_taxi.*`, write `nyc_taxi_dev.*` only.
  No agent identity holds `DROP` on any catalog.
- ✅ Encryption at rest and in transit is provided by Databricks-managed storage and TLS.
- ✅ **No secrets in the context window.** Credentials come from a secret scope or `.env`; the
  committed `.env.example` carries names with no values.
- — Tenant partitioning of vector/memory stores: **not applicable** — single tenant, no vector store.

## Pillar 3 — Model

- ✅ Prompts and rule files (`AGENTS.md`, `CLAUDE.md`, `.agent/skills/`, `configs/*.yml`) are
  version-controlled and reviewed as source. In an agentic workflow these *are* the source code.
- ▶ Prompt-injection surface is small but non-zero: the agent reads a downloaded CSV and profiling
  output. Treat any string originating in data as **data, never instruction** — a column value or
  filename must never be executed or followed.
- — LLM firewall: **deferred.** No interactive end-user surface; the only operator is the developer.

## Pillar 4 — Application & runtime

- ✅ **Deterministic pre-commit hook** (`.githooks/pre-commit`): blocks Databricks PAT patterns,
  `.env` files, and raw data files. Verified to actually fire — see `EVAL_PLAN.md` §1.
- ▶ Post-edit hook in `.claude/settings.json` runs the formatter/linter on changed Python.
- ▶ Build-time gate: any `TBD_PENDING_PROFILING` threshold reaching a Gold build fails it (BDD-05).
  This is a software constraint, not a prose rule — an unapproved threshold *cannot* ship.
- — Agent gateway for A2A: **not applicable** — single agent, no A2A (see `docs/tools-plan.md` §2).

## Pillar 5 — Identity & access (IAM) · *production depth, not tier depth*

- ▶ **Prefer an OAuth service principal (M2M)** over a personal access token. A PAT carries the
  human's full workspace privileges into every agent action — the textbook confused deputy.
- ▶ Credentials are scoped to the dev schema and rotated; no long-lived token in any config file.
- ▶ If Free Edition forces a PAT, treat it as a compensating control, not an equivalent: short
  expiry, single workspace, rotate on any suspicion, never share across machines.
- — SPIFFE-style cryptographic agent identity: **deferred.** Warranted for a fleet of agents; this
  is one developer with one workspace.

## Pillar 6 — Observability & SecOps

- ▶ Tool calls logged with inputs, outputs and duration (`docs/tools-plan.md` §3).
- ▶ Databricks `statement_id` captured per query for traceability in query history.
- ▶ Every pipeline run writes a `profile_run` / audit row: run id, source hash, row counts, status.
- — Red/Blue/Green teaming programme: **deferred.** No adversary model and no production traffic.
  The adversarial *eval* cases in `EVAL_PLAN.md` §2 cover the realistic failure surface instead.

## Pillar 7 — Governance · *the one that actually protects this project*

- ✅ **Immutable audit trail:** git history for definitions, Delta time travel for data, quarantine
  table for every rejected row. Every action traces to a commit and its author.
- ▶ **Logic review over one-click approval:** a change to a KPI formula must be reviewed in plain
  language — what the number meant before, what it means now, who is affected. "The build passed"
  is not "the definition is still correct."
- ✅ KPI and DQ definitions are version-controlled and require a contract bump to change
  (contract §20; enforced by the planned `kpi-contract-guard` skill).
- — EU AI Act / regulatory assessment: **not applicable.** No automated decisions about people, no
  high-risk autonomy; a portfolio analytics platform on public data.

---

## High-stakes actions requiring human-in-the-loop

> Enforced by hook or build gate where marked — prose alone is not a guarantee.

- [x] **Committing a secret** — blocked by pre-commit hook ✅
- [x] **Committing raw/licensed data** — blocked by pre-commit hook ✅
- [ ] **Changing a KPI definition** — requires contract version bump ▶
- [ ] **Setting a TBD threshold** — requires profiling evidence + approval; build gate ▶
- [ ] **Approving a data-quality exception** — human only, never the agent
- [ ] **`DROP` / `DELETE` on any Delta table** — explicit confirmation naming the table
- [ ] **Writing outside the dev schema** — explicit confirmation
- [ ] **Scheduling a recurring job / deploying** — explicit confirmation

## Primary failure mode guarded against

- ✅ **No auto-approve ("YOLO") on high-stakes actions.** The recurring real-world incident is an
  under-specified agent filling a gap with whatever string is in its context — a hallucinated
  catalog name, a plausible-looking threshold, a stale workspace URL — and taking a real action
  nobody asked for. `AGENTS.md` instructs the agent to **stop and ask** rather than fill the gap;
  the hooks and the build gate make the highest-consequence versions of that mistake impossible
  rather than merely discouraged.

## Deferral summary

Five items are deferred: kernel-level sandbox, tenant partitioning, LLM firewall, SPIFFE identity,
Red/Blue/Green programme, plus the regulatory assessment as not-applicable. Every one is deferred
because of a **specific** absent condition — no untrusted code, single tenant, no end-user surface,
single operator, no adversary, no automated decisions about people. If any of those conditions
changes, the corresponding item returns.
