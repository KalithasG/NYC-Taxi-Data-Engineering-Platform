/*
  Mart: gold.trip_performance   KPI-001..006, plus KPI-016/017 once their thresholds exist.
  Grain: reporting period x date x vendor x time_of_day.

  Formulas come from configs/kpi_config.yml — read them there, do not restate one from memory.
  Idempotent: full replace, so a rerun over unchanged Silver produces identical values (BDD-04).
*/
SELECT
    pickup_date,
    vendor_id,
    time_of_day,
    day_of_week,
    is_weekend,

    COUNT(DISTINCT id)                                                    AS kpi_001_total_trips,
    ROUND(AVG(trip_duration), 4)                                          AS kpi_002_avg_duration_seconds,
    ROUND(AVG(trip_duration) / 60.0, 4)                                   AS kpi_002_avg_duration_minutes,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY trip_duration), 4) AS kpi_003_median_duration_seconds,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY trip_duration) / 60.0, 4)
                                                                          AS kpi_003_median_duration_minutes,
    ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration), 4) AS kpi_004_p90_duration_seconds,
    ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY trip_duration) / 60.0, 4)
                                                                          AS kpi_004_p90_duration_minutes,

    -- KPI-005 / KPI-006 exclude rows with unusable coordinates, per their filter in kpi_config.
    ROUND(AVG(CASE WHEN estimated_distance_km IS NOT NULL
                   THEN estimated_distance_km END), 6)                    AS kpi_005_avg_estimated_distance_km,
    ROUND(AVG(CASE WHEN estimated_speed_kmh IS NOT NULL AND trip_duration > 0
                   THEN estimated_speed_kmh END), 6)                      AS kpi_006_avg_estimated_speed_kmh,

    {% if threshold_is_approved('long_trip_seconds') | trim == 'True' %}
    ROUND(100.0 * SUM(CASE WHEN trip_duration > {{ var('long_trip_seconds') }} THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*), 0), 4)                                       AS kpi_016_long_trip_rate_pct,
    {% else %}
    {{ withheld_note('KPI-016', 'long_trip_seconds') }},
    {% endif %}

    {% if threshold_is_approved('low_speed_kmh') | trim == 'True' %}
    ROUND(100.0 * SUM(CASE WHEN estimated_speed_kmh IS NOT NULL
                            AND estimated_speed_kmh < {{ var('low_speed_kmh') }}
                           THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN estimated_speed_kmh IS NOT NULL THEN 1 ELSE 0 END), 0), 4)
                                                                          AS kpi_017_low_speed_rate_pct,
    {% else %}
    {{ withheld_note('KPI-017', 'low_speed_kmh') }},
    {% endif %}

    COUNT(*)                                                              AS row_count
FROM {{ ref('silver_trips') }}
GROUP BY pickup_date, vendor_id, time_of_day, day_of_week, is_weekend
