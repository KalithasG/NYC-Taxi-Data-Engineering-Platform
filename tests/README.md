# tests/

**Deterministic** data tests — input → expected output, checked by code. Distinct from `evals/`,
which checks the non-deterministic agent behaviour.

| Directory | Covers |
|---|---|
| `data_quality/` | DQ-001..015 behaviour; quarantine auditability; BDD-02, BDD-03, BDD-06 |
| `transformations/` | Bronze immutability, Silver determinism; BDD-01 |
| `kpi/` | KPI formulas against the golden dataset; idempotency and the threshold gate; BDD-04, BDD-05 |

The full mapping from BDD scenario to owning test is in `EVAL_PLAN.md` §1.

Run with `pytest` (9.1.1). dbt model tests run via `dbt test`.
