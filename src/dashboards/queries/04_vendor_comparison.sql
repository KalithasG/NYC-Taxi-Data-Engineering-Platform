-- Vendor comparison — KPI-013, KPI-014, KPI-015.
--
-- P50/P90/P95 sit next to the average deliberately. Trip-duration distributions are
-- right-skewed and vendor trip mixes differ, so a chart comparing averages alone invites a
-- conclusion the data does not support (contract §9). Plot the percentiles, not just the mean.
SELECT
    vendor_id,
    vendor_trips,
    ROUND(kpi_013_vendor_trip_share_pct, 2)      AS trip_share_pct,
    ROUND(kpi_014_avg_duration_seconds / 60.0, 1) AS avg_duration_min,
    ROUND(median_duration_seconds      / 60.0, 1) AS median_duration_min,
    ROUND(kpi_015_p90_duration_seconds / 60.0, 1) AS p90_duration_min,
    ROUND(avg_estimated_distance_km, 2)           AS avg_estimated_distance_km,
    ROUND(avg_estimated_speed_kmh, 1)             AS avg_estimated_speed_kmh
FROM gold.vendor_performance
ORDER BY vendor_id
