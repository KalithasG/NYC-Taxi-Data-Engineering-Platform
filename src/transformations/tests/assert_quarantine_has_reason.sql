-- DQ-015: every rejected row is auditable — it carries a rule id and a reason.
SELECT id, rule_id, quarantine_reason
FROM {{ ref('silver_trips_quarantine') }}
WHERE rule_id IS NULL OR quarantine_reason IS NULL
