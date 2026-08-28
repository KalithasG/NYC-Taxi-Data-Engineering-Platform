-- BDD-02 / DQ-015: no silent data loss. total = valid + quarantined, per batch.
-- A row here means rows disappeared somewhere between Bronze and the Silver split.
SELECT source_hash, total_records, valid_records, quarantined_records
FROM {{ ref('data_quality') }}
WHERE total_records <> valid_records + quarantined_records
