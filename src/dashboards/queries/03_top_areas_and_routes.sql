-- Top pickup areas, drop-off areas and routes — KPI-010, KPI-011, KPI-012.
-- "Top" is a filter on rank, not a value baked into the mart, so the same query serves top-1
-- or top-20 by changing one number.
SELECT
    dimension,
    area_key,
    trip_count,
    ROUND(avg_duration_seconds    / 60.0, 1) AS avg_duration_min,
    ROUND(median_duration_seconds / 60.0, 1) AS median_duration_min,
    ROUND(p90_duration_seconds    / 60.0, 1) AS p90_duration_min,
    ROUND(avg_estimated_distance_km, 2)      AS avg_estimated_distance_km,
    ROUND(avg_estimated_speed_kmh, 1)        AS avg_estimated_speed_kmh,
    rank_in_dimension
FROM gold.geographic_metrics
WHERE rank_in_dimension <= 10
ORDER BY dimension, rank_in_dimension
