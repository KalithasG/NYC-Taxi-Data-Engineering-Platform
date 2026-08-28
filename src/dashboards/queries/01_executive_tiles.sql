-- Executive tile row — KPI-001..006 plus the data-quality score.
-- Layout: kpi-discussion.md §11. One row, one value per tile.
--
-- Every KPI is re-aggregated from the Gold mart rather than averaged across its rows: taking
-- AVG() of a per-group average silently weights small groups equally with large ones. Duration
-- percentiles are recomputed from silver_trips for the same reason — a median of medians is not
-- a median.
SELECT
    (SELECT SUM(kpi_001_total_trips) FROM gold.trip_performance)          AS kpi_001_total_trips,

    (SELECT ROUND(AVG(trip_duration) / 60.0, 1) FROM silver_trips)        AS kpi_002_avg_duration_min,
    (SELECT ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY trip_duration) / 60.0, 1)
       FROM silver_trips)                                                 AS kpi_003_median_duration_min,
    (SELECT ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration) / 60.0, 1)
       FROM silver_trips)                                                 AS kpi_004_p90_duration_min,

    -- Geodesic. The tile label must read "estimated", never "actual" or "road" (BDD-07).
    (SELECT ROUND(AVG(estimated_distance_km), 2) FROM silver_trips)       AS kpi_005_avg_estimated_distance_km,
    (SELECT ROUND(AVG(estimated_speed_kmh), 1) FROM silver_trips)         AS kpi_006_avg_estimated_speed_kmh,

    (SELECT kpi_009_peak_hour FROM gold.demand_metrics
      ORDER BY kpi_009_peak_hour_trip_count DESC, pickup_date LIMIT 1)    AS kpi_009_peak_hour,
    -- Recomputed across all batches rather than reading one row: with more than one batch
    -- ingested, picking a single row shows that batch's score and calls it the platform's.
    (SELECT ROUND(100.0 * SUM(valid_records) / NULLIF(SUM(total_records), 0), 2)
       FROM gold.data_quality)                                            AS kpi_018_data_quality_pct
