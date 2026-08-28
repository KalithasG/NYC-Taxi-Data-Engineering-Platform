/*
  Mart: gold.data_quality   KPI-018 Quality Score · KPI-019 Invalid Rate · KPI-020 Duplicate Rate
  Grain: batch (source_hash).

  Two things here are easy to get subtly wrong:

  1. KPI-020 must count duplicates from the ORIGINAL, pre-deduplication population. Reading the
     deduplicated Silver table would report zero forever and make a dirty batch look clean.
     It therefore reads silver_dq_evaluated, which still holds every row.
  2. The reconciliation total = valid + quarantined is emitted as a column, not assumed. If it
     ever stops holding, something is dropping rows silently — the failure DQ-015 exists to catch.
*/
WITH all_rows AS (
    SELECT source_hash, source_file, is_valid_trip, id,
           COUNT(*) OVER (PARTITION BY id) AS id_occurrences
    FROM {{ ref('silver_dq_evaluated') }}
),
agg AS (
    SELECT
        source_hash,
        MIN(source_file)                                              AS source_file,
        COUNT(*)                                                      AS total_records,
        SUM(CASE WHEN is_valid_trip THEN 1 ELSE 0 END)                AS valid_records,
        SUM(CASE WHEN is_valid_trip THEN 0 ELSE 1 END)                AS quarantined_records,
        -- A NULL id is a missing primary key (DQ-001), not a duplicate. Spark groups NULLs
        -- together in a window partition, so without this guard every null-id row would be
        -- counted as a duplicate of every other, inflating KPI-020 and conflating two
        -- different data problems.
        SUM(CASE WHEN id IS NOT NULL AND id_occurrences > 1 THEN 1 ELSE 0 END)
                                                                      AS duplicate_records
    FROM all_rows GROUP BY source_hash
),
components AS (
    SELECT
        source_hash,
        COUNT(*)                                                             AS n,
        SUM(CASE WHEN pass_dq_001 AND pass_dq_004 AND pass_dq_005 THEN 1 ELSE 0 END) AS completeness_ok,
        SUM(CASE WHEN pass_dq_002 THEN 1 ELSE 0 END)                         AS uniqueness_ok,
        SUM(CASE WHEN pass_dq_003 AND pass_dq_007 THEN 1 ELSE 0 END)         AS validity_ok,
        SUM(CASE WHEN pass_dq_006 THEN 1 ELSE 0 END)                         AS consistency_ok,
        SUM(CASE WHEN pass_dq_009 AND pass_dq_010 THEN 1 ELSE 0 END)         AS geographic_ok
    FROM {{ ref('silver_dq_evaluated') }} GROUP BY source_hash
)
SELECT
    a.source_hash,
    a.source_file,
    a.total_records,
    a.valid_records,
    a.quarantined_records,
    a.duplicate_records,

    ROUND(100.0 * a.valid_records       / NULLIF(a.total_records, 0), 4) AS kpi_018_data_quality_score_pct,
    ROUND(100.0 * a.quarantined_records / NULLIF(a.total_records, 0), 4) AS kpi_019_invalid_record_rate_pct,
    ROUND(100.0 * a.duplicate_records   / NULLIF(a.total_records, 0), 4) AS kpi_020_duplicate_rate_pct,

    -- Component scores reported separately, before any weighted blend (profiling §27):
    -- one number hides which dimension is actually failing.
    ROUND(100.0 * c.completeness_ok / NULLIF(c.n, 0), 4) AS completeness_score_pct,
    ROUND(100.0 * c.uniqueness_ok   / NULLIF(c.n, 0), 4) AS uniqueness_score_pct,
    ROUND(100.0 * c.validity_ok     / NULLIF(c.n, 0), 4) AS validity_score_pct,
    ROUND(100.0 * c.consistency_ok  / NULLIF(c.n, 0), 4) AS consistency_score_pct,
    ROUND(100.0 * c.geographic_ok   / NULLIF(c.n, 0), 4) AS geographic_validity_score_pct,

    (a.total_records = a.valid_records + a.quarantined_records) AS reconciles
FROM agg a JOIN components c ON c.source_hash = a.source_hash
