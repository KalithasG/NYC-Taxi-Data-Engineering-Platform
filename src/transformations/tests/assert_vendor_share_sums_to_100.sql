-- KPI-013 acceptance criterion (contract §9): vendor shares sum to ~100%.
SELECT SUM(kpi_013_vendor_trip_share_pct) AS total_share
FROM {{ ref('vendor_performance') }}
HAVING ABS(SUM(kpi_013_vendor_trip_share_pct) - 100.0) > 0.01
