/*
  Mart: gold.geographic_metrics   KPI-010 Top Pickup Area · KPI-011 Top Drop-off Area · KPI-012 Top Route

  Emitted as ranked rows rather than a single winner. "Top" is then a filter (rank = 1) rather
  than a value baked into the table, so the same mart answers "top 10 routes" without a rebuild.

  Route rows also carry the companion metrics the contract requires for high-volume routes (§8):
  count, avg / median / p90 duration, avg estimated distance and speed.
*/
WITH pickup AS (
    SELECT 'pickup_area' AS dimension, pickup_area AS area_key,
           COUNT(DISTINCT id) AS trip_count,
           CAST(NULL AS DOUBLE) AS avg_duration_seconds,
           CAST(NULL AS DOUBLE) AS median_duration_seconds,
           CAST(NULL AS DOUBLE) AS p90_duration_seconds,
           CAST(NULL AS DOUBLE) AS avg_estimated_distance_km,
           CAST(NULL AS DOUBLE) AS avg_estimated_speed_kmh
    FROM {{ ref('silver_trips') }} GROUP BY pickup_area
),
dropoff AS (
    SELECT 'dropoff_area', dropoff_area, COUNT(DISTINCT id),
           NULL, NULL, NULL, NULL, NULL
    FROM {{ ref('silver_trips') }} GROUP BY dropoff_area
),
route AS (
    SELECT 'route', route_key, COUNT(DISTINCT id),
           ROUND(AVG(trip_duration), 4),
           ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY trip_duration), 4),
           ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration), 4),
           ROUND(AVG(estimated_distance_km), 6),
           ROUND(AVG(estimated_speed_kmh), 6)
    FROM {{ ref('silver_trips') }} GROUP BY route_key
),
unioned AS (
    SELECT * FROM pickup
    UNION ALL SELECT * FROM dropoff
    UNION ALL SELECT * FROM route
)
SELECT
    dimension, area_key, trip_count,
    avg_duration_seconds, median_duration_seconds, p90_duration_seconds,
    avg_estimated_distance_km, avg_estimated_speed_kmh,
    -- area_key as the tiebreak keeps the ranking stable across runs (goal G2).
    ROW_NUMBER() OVER (PARTITION BY dimension ORDER BY trip_count DESC, area_key ASC) AS rank_in_dimension
FROM unioned
