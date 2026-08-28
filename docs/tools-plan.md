# Tools & Interoperability Plan — NYC Taxi Data Engineering Platform

**Tier:** structured · **Stage 3** of the agentic-engineering workflow

> The model reasons; tools act. This decides what the agent can reach, with what scope, and how
> failures surface. Principle: **discover before you build** — reuse an existing MCP server rather
> than writing bespoke glue.

---

## 1. MCP servers

| # | Capability | Server | Least-privilege scope | Status |
|---|---|---|---|---|
| 1 | Databricks SQL + Unity Catalog | Databricks MCP (managed) or `databricks-sdk` wrapper | Read: `nyc_taxi.*`. Write: `nyc_taxi_dev.*` only. No `DROP`. No workspace admin. | **Verify availability on Free Edition** |
| 2 | Repository | GitHub MCP | Single repo. Read + PR. No org admin, no force-push to default. | Available in session |
| 3 | Local filesystem | Built-in | Repo working directory only. | Available |

**Server 1 is the one to confirm.** Databricks publishes managed MCP servers (Unity Catalog
functions, Genie spaces, vector search) and there are community `databricks-mcp` servers, but
**whether they are enabled on Free Edition is unconfirmed** — treat it as spec OQ-3's sibling.
Resolve it before relying on MCP for warehouse access.

*Fallback if unavailable:* drive Databricks through `databricks-sdk` (0.133.0) and
`databricks-sql-connector` (4.4.0) from local scripts in `src/`. This costs the agent nothing in
capability — it just means tool calls become script runs. Do **not** invent an MCP server that is
not there; fail closed and say so.

### Lifecycle for server 1

1. **Discovery** — check the Databricks MCP catalog and the workspace's enabled features. Record
   the answer in this file rather than in chat, so the next session does not re-derive it.
2. **Configuration** — register with a **service principal (OAuth M2M)** where Free Edition
   supports it; a PAT tied to a human account is the confused-deputy risk called out in
   `SECURITY_CHECKLIST.md` Pillar 5. Pin the server version. Scope to the catalogs above.
3. **Connection** — confirm the agent can *list* the tools and run one read-only query
   (`SELECT 1`) before trusting it with a transformation.

### Credential handling (non-negotiable)

- Credentials live in a Databricks secret scope or a local `.env` — **never** in a config file,
  notebook, dbt profile, or commit. `.env.example` documents the variable *names* only.
- `profiles.yml` for dbt reads from environment variables; the committed version contains no
  secret values.
- The pre-commit hook blocks `dapi[0-9a-f]{32}` and `.env`. Verified working — see `EVAL_PLAN.md`.

---

## 2. Agent-to-Agent (A2A)

**Not applicable. Deliberately.**

This is a single-agent project: one well-harnessed agent building a batch data pipeline. The
workflow's own guidance is not to invent a virtual workforce a single agent could handle — every
extra agent adds failure surface without adding capability here.

Downstream consumers read the Gold marts as data — a table in Unity Catalog, not an Agent Card.
That is the right boundary for an analytics platform: consumers depend on governed tables, not on
this agent being available.

Revisit only if a consumer genuinely needs to call this platform at runtime. None does today.

---

## 3. Debugging & observability for the tool layer

- **Confirm the server before blaming the model.** If a tool call fails, check in order: server
  reachable → tool list loads → credentials valid → scope covers the target → then the prompt.
- **Log every tool call** — inputs, outputs, duration. This feeds the observability section of
  `EVAL_PLAN.md`; without it there is no way to tell a genuine success from quiet drift.
- **Fail closed.** If a tool cannot authenticate or the target is out of scope, surface the error.
  Never let the agent improvise a workaround — e.g. switching to a different catalog because the
  intended one returned a permission error.
- **Describe *when* to call each tool**, not just what it does. The prose around a tool drives
  routing as much as the tool signature.
- **Databricks-specific:** serverless query failures often surface as generic errors. Capture the
  `statement_id` on every query so the failure can be traced in the query history UI.
