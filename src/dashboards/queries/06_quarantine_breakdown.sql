-- Quarantine breakdown by rule — the auditable half of DQ-015.
--
-- This panel is what makes "no silent data loss" visible rather than asserted: every rejected
-- row appears here under the rule that rejected it, and the totals reconcile with the quality
-- panel above.
SELECT
    rule_id,
    quarantine_reason,
    COUNT(*) AS rejected_rows,
    ROUND(100.0 * COUNT(*) / (SELECT SUM(total_records) FROM gold.data_quality), 4)
        AS pct_of_batch
FROM silver_trips_quarantine
GROUP BY rule_id, quarantine_reason
ORDER BY rejected_rows DESC
