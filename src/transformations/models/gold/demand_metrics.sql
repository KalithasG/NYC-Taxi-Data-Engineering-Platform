/*
  Mart: gold.demand_metrics   KPI-007 Trips Per Day · KPI-008 Trips Per Hour · KPI-009 Peak Hour

  Grain is date + hour, the extended grain the contract recommends (§7): it serves the daily
  time series and the aggregate hourly profile from one table, so the two can never disagree.
*/
WITH by_hour AS (
    SELECT pickup_date, pickup_hour, vendor_id, day_of_week,
           COUNT(DISTINCT id) AS trip_count
    FROM {{ ref('silver_trips') }}
    GROUP BY pickup_date, pickup_hour, vendor_id, day_of_week
),
daily AS (
    SELECT pickup_date, SUM(trip_count) AS kpi_007_trips_per_day
    FROM by_hour GROUP BY pickup_date
),
peak AS (
    -- KPI-009 ARGMAX. Ties broken by the lowest hour so the result is deterministic across
    -- runs — an ARGMAX with an arbitrary tiebreak would violate goal G2.
    SELECT pickup_date,
           MIN_BY(pickup_hour, -trip_count) AS kpi_009_peak_hour,
           MAX(trip_count)                  AS kpi_009_peak_hour_trip_count
    FROM (SELECT pickup_date, pickup_hour, SUM(trip_count) AS trip_count
          FROM by_hour GROUP BY pickup_date, pickup_hour)
    GROUP BY pickup_date
)
SELECT
    h.pickup_date,
    h.pickup_hour,
    h.vendor_id,
    h.day_of_week,
    h.trip_count            AS kpi_008_trips_per_hour,
    d.kpi_007_trips_per_day,
    p.kpi_009_peak_hour,
    p.kpi_009_peak_hour_trip_count
FROM by_hour h
JOIN daily d ON d.pickup_date = h.pickup_date
JOIN peak  p ON p.pickup_date = h.pickup_date
