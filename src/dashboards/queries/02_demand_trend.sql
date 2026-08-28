-- Daily and hourly demand trend — KPI-007, KPI-008.
-- Two series from one table: the daily line and the hour-of-day profile can never disagree
-- because they share a grain.
SELECT
    pickup_date,
    pickup_hour,
    SUM(kpi_008_trips_per_hour) AS trips_per_hour,
    MAX(kpi_007_trips_per_day)  AS trips_per_day
FROM gold.demand_metrics
GROUP BY pickup_date, pickup_hour
ORDER BY pickup_date, pickup_hour
