/*
  The trusted trip population. One row per valid trip id.

  Outlier flags are computed here and are exactly that — flags. DQ-014 forbids removing a row
  because it is statistically extreme: a very long trip, a very slow trip and a zero-distance
  trip can all be real (profiling §2). KPI-001 counts them; a KPI that wants them excluded
  says so in its own filter.
*/
SELECT
    id, vendor_id,
    pickup_datetime, dropoff_datetime,
    passenger_count,
    pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude,
    store_and_fwd_flag_raw AS store_and_fwd_flag,
    trip_duration, trip_duration_minutes,
    pickup_date, pickup_year, pickup_month, pickup_week, pickup_day,
    day_of_week, pickup_hour, is_weekend, time_of_day,
    estimated_distance_km, estimated_speed_kmh,
    observed_duration_seconds, duration_difference_seconds,

    -- Geographic buckets. Zone polygons are a documented future enhancement (contract §8);
    -- until then an area is a rounded coordinate cell, and the rounding IS the definition.
    CONCAT(CAST(ROUND(pickup_latitude, 2) AS STRING), ',',
           CAST(ROUND(pickup_longitude, 2) AS STRING))          AS pickup_area,
    CONCAT(CAST(ROUND(dropoff_latitude, 2) AS STRING), ',',
           CAST(ROUND(dropoff_longitude, 2) AS STRING))         AS dropoff_area,
    CONCAT(CAST(ROUND(pickup_latitude, 2) AS STRING), ',',
           CAST(ROUND(pickup_longitude, 2) AS STRING), ' -> ',
           CAST(ROUND(dropoff_latitude, 2) AS STRING), ',',
           CAST(ROUND(dropoff_longitude, 2) AS STRING))         AS route_key,

    is_passenger_count_anomaly,
    is_store_fwd_flag_anomaly,
    coordinate_anomaly,

    {% if threshold_is_approved('extreme_duration_seconds') | trim == 'True' %}
    (trip_duration > {{ var('extreme_duration_seconds') }})     AS is_duration_outlier,
    {% else %}
    CAST(NULL AS BOOLEAN)                                       AS is_duration_outlier,
    {% endif %}

    {% if threshold_is_approved('low_speed_kmh') | trim == 'True' %}
    (estimated_speed_kmh IS NOT NULL
        AND estimated_speed_kmh < {{ var('low_speed_kmh') }})   AS is_speed_outlier,
    {% else %}
    CAST(NULL AS BOOLEAN)                                       AS is_speed_outlier,
    {% endif %}

    TRUE                                                        AS is_valid_trip,
    source_file, source_hash, ingested_at
FROM {{ ref('silver_dq_evaluated') }}
WHERE is_valid_trip
