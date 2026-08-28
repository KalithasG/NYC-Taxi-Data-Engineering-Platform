-- Data quality panel — KPI-018, KPI-019, KPI-020, plus the component scores.
--
-- The component scores are shown separately rather than blended. A single quality number hides
-- which dimension is failing, which is the one thing an operator needs to know (profiling §27).
-- `reconciles` is on the panel because a false there means rows are disappearing silently.
SELECT
    source_hash,
    source_file,
    total_records,
    valid_records,
    quarantined_records,
    duplicate_records,
    ROUND(kpi_018_data_quality_score_pct, 3)  AS kpi_018_quality_score_pct,
    ROUND(kpi_019_invalid_record_rate_pct, 3) AS kpi_019_invalid_rate_pct,
    ROUND(kpi_020_duplicate_rate_pct, 3)      AS kpi_020_duplicate_rate_pct,
    ROUND(completeness_score_pct, 3)          AS completeness_pct,
    ROUND(uniqueness_score_pct, 3)            AS uniqueness_pct,
    ROUND(validity_score_pct, 3)              AS validity_pct,
    ROUND(consistency_score_pct, 3)           AS consistency_pct,
    ROUND(geographic_validity_score_pct, 3)   AS geographic_validity_pct,
    reconciles
FROM gold.data_quality
ORDER BY source_hash
