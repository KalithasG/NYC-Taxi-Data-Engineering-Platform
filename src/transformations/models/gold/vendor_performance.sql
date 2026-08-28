/*
  Mart: gold.vendor_performance   KPI-013 Trip Share · KPI-014 Avg Duration · KPI-015 P90 Duration

  P90 sits alongside the average deliberately. Trip-duration distributions are right-skewed and
  vendor trip mixes differ, so comparing vendors on averages alone invites a conclusion the data
  does not support (contract §9, profiling §24).
*/
WITH per_vendor AS (
    SELECT
        vendor_id,
        COUNT(DISTINCT id)                                                    AS vendor_trips,
        ROUND(AVG(trip_duration), 4)                                          AS kpi_014_avg_duration_seconds,
        ROUND(AVG(trip_duration) / 60.0, 4)                                   AS kpi_014_avg_duration_minutes,
        ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration), 4) AS kpi_015_p90_duration_seconds,
        ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration) / 60.0, 4)
                                                                              AS kpi_015_p90_duration_minutes,
        ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY trip_duration), 4) AS median_duration_seconds,
        ROUND(AVG(estimated_distance_km), 6)                                  AS avg_estimated_distance_km,
        ROUND(AVG(estimated_speed_kmh), 6)                                    AS avg_estimated_speed_kmh
    FROM {{ ref('silver_trips') }}
    GROUP BY vendor_id
),
total AS (SELECT SUM(vendor_trips) AS total_trips FROM per_vendor)
SELECT
    v.vendor_id,
    v.vendor_trips,
    t.total_trips,
    ROUND(100.0 * v.vendor_trips / NULLIF(t.total_trips, 0), 4) AS kpi_013_vendor_trip_share_pct,
    v.kpi_014_avg_duration_seconds,
    v.kpi_014_avg_duration_minutes,
    v.kpi_015_p90_duration_seconds,
    v.kpi_015_p90_duration_minutes,
    v.median_duration_seconds,
    v.avg_estimated_distance_km,
    v.avg_estimated_speed_kmh
FROM per_vendor v CROSS JOIN total t
