{{ config(materialized='view') }}
/*
  Typing and derivation only — no rows are removed here.

  Keeping this separate from rule evaluation means the DQ rules and the quarantine both read
  exactly the same derived values, so `total = valid + quarantined` can actually hold.
  Deterministic throughout: no current_timestamp(), no rand(), no unordered LIMIT.
*/
WITH cast_source AS (
    SELECT
        NULLIF(TRIM(id), '')                                   AS id,
        CAST(vendor_id AS INT)                                 AS vendor_id,
        CAST(NULLIF(TRIM(pickup_datetime),  '') AS TIMESTAMP)  AS pickup_datetime,
        CAST(NULLIF(TRIM(dropoff_datetime), '') AS TIMESTAMP)  AS dropoff_datetime,
        CAST(passenger_count AS INT)                           AS passenger_count,
        CAST(NULLIF(TRIM(CAST(pickup_longitude  AS STRING)), '') AS DOUBLE) AS pickup_longitude,
        CAST(NULLIF(TRIM(CAST(pickup_latitude   AS STRING)), '') AS DOUBLE) AS pickup_latitude,
        CAST(NULLIF(TRIM(CAST(dropoff_longitude AS STRING)), '') AS DOUBLE) AS dropoff_longitude,
        CAST(NULLIF(TRIM(CAST(dropoff_latitude  AS STRING)), '') AS DOUBLE) AS dropoff_latitude,
        UPPER(TRIM(store_and_fwd_flag))                        AS store_and_fwd_flag_raw,
        TRIM(store_and_fwd_flag)                               AS store_and_fwd_flag_original,
        CAST(trip_duration AS BIGINT)                          AS trip_duration,
        source_file, source_hash, ingested_at
    FROM {{ source('bronze', 'bronze_trips') }}
),

derived AS (
    SELECT
        *,
        trip_duration / 60.0                        AS trip_duration_minutes,
        DATE(pickup_datetime)                       AS pickup_date,
        YEAR(pickup_datetime)                       AS pickup_year,
        MONTH(pickup_datetime)                      AS pickup_month,
        WEEKOFYEAR(pickup_datetime)                 AS pickup_week,
        DAY(pickup_datetime)                        AS pickup_day,
        DATE_FORMAT(pickup_datetime, 'EEEE')        AS day_of_week,
        HOUR(pickup_datetime)                       AS pickup_hour,
        {{ is_weekend('pickup_datetime') }}         AS is_weekend,
        {{ time_of_day('pickup_datetime') }}        AS time_of_day,

        -- Geodesic (Haversine), NOT road distance. See BDD-07.
        CASE
            WHEN pickup_latitude IS NULL OR pickup_longitude IS NULL
              OR dropoff_latitude IS NULL OR dropoff_longitude IS NULL THEN CAST(NULL AS DOUBLE)
            ELSE {{ haversine_km('pickup_latitude','pickup_longitude',
                                 'dropoff_latitude','dropoff_longitude') }}
        END                                         AS estimated_distance_km,

        -- Observed interval, for the duration-consistency comparison (profiling §11).
        CASE
            WHEN pickup_datetime IS NULL OR dropoff_datetime IS NULL THEN CAST(NULL AS BIGINT)
            ELSE BIGINT(UNIX_TIMESTAMP(dropoff_datetime) - UNIX_TIMESTAMP(pickup_datetime))
        END                                         AS observed_duration_seconds
    FROM cast_source
)

SELECT
    *,
    CASE
        WHEN estimated_distance_km IS NULL OR trip_duration IS NULL OR trip_duration <= 0
            THEN CAST(NULL AS DOUBLE)
        ELSE ROUND(estimated_distance_km / (trip_duration / 3600.0), 6)
    END                                             AS estimated_speed_kmh,
    CASE
        WHEN observed_duration_seconds IS NULL OR trip_duration IS NULL THEN CAST(NULL AS BIGINT)
        ELSE observed_duration_seconds - trip_duration
    END                                             AS duration_difference_seconds
FROM derived
