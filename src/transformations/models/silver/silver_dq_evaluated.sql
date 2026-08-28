{{ config(materialized='view') }}
/*
  Evaluates the data-quality rules from configs/quality_rules.yml against every row.

  Nothing is dropped here either — each rule contributes a boolean, and the split into valid
  and quarantined happens downstream. That ordering is what makes DQ-015 (every rejection
  auditable) and the reconciliation total = valid + quarantined achievable rather than hoped for.

  Four rules depend on a TBD_PENDING_PROFILING parameter (DQ-003, DQ-008, DQ-009, DQ-010).
  Where the parameter is unset, the decidable part of the rule is still applied — a null or
  worldwide-impossible coordinate is wrong regardless of where NYC's bounds fall — and the
  undecidable part is recorded as blocked rather than silently passed.
*/
WITH e AS (
    SELECT
        *,
        -- ---- hard rules, decidable today ----
        (id IS NOT NULL)                                                    AS pass_dq_001,
        (COUNT(*) OVER (PARTITION BY id) = 1)                               AS pass_dq_002,
        (pickup_datetime  IS NOT NULL)                                      AS pass_dq_004,
        (dropoff_datetime IS NOT NULL)                                      AS pass_dq_005,
        (dropoff_datetime IS NULL OR pickup_datetime IS NULL
            OR dropoff_datetime >= pickup_datetime)                         AS pass_dq_006,
        (trip_duration IS NOT NULL AND trip_duration > 0)                   AS pass_dq_007,
        (estimated_distance_km IS NULL OR estimated_distance_km >= 0)       AS pass_dq_012,
        (estimated_speed_kmh   IS NULL OR estimated_speed_kmh   >= 0)       AS pass_dq_013,

        -- ---- vendor domain: DQ-003, parameter pending profiling ----
        {% if threshold_is_approved('vendor_domain') | trim == 'True' %}
        (vendor_id IN ({{ var('vendor_domain') }}))                         AS pass_dq_003,
        {% else %}
        (vendor_id IS NOT NULL)                                             AS pass_dq_003,
        {% endif %}

        -- ---- coordinates: DQ-009 / DQ-010. Worldwide bounds are necessary but insufficient
        --      (profiling §14); the NYC region bound is the pending part.
        (pickup_latitude  IS NOT NULL AND pickup_longitude  IS NOT NULL
            AND pickup_latitude  BETWEEN -90  AND 90
            AND pickup_longitude BETWEEN -180 AND 180
            AND NOT (pickup_latitude = 0 AND pickup_longitude = 0)
        {% if threshold_is_approved('nyc_bounds') | trim == 'True' %}
            AND pickup_latitude  BETWEEN {{ var('nyc_bounds').lat_min }} AND {{ var('nyc_bounds').lat_max }}
            AND pickup_longitude BETWEEN {{ var('nyc_bounds').lon_min }} AND {{ var('nyc_bounds').lon_max }}
        {% endif %}
        )                                                                   AS pass_dq_009,
        (dropoff_latitude IS NOT NULL AND dropoff_longitude IS NOT NULL
            AND dropoff_latitude  BETWEEN -90  AND 90
            AND dropoff_longitude BETWEEN -180 AND 180
            AND NOT (dropoff_latitude = 0 AND dropoff_longitude = 0)
        {% if threshold_is_approved('nyc_bounds') | trim == 'True' %}
            AND dropoff_latitude  BETWEEN {{ var('nyc_bounds').lat_min }} AND {{ var('nyc_bounds').lat_max }}
            AND dropoff_longitude BETWEEN {{ var('nyc_bounds').lon_min }} AND {{ var('nyc_bounds').lon_max }}
        {% endif %}
        )                                                                   AS pass_dq_010,

        -- ---- flag-only rules: the row STAYS in the valid population ----
        {% if threshold_is_approved('passenger_count_domain') | trim == 'True' %}
        (passenger_count IS NOT NULL
            AND passenger_count BETWEEN {{ var('passenger_count_domain').min }}
                                    AND {{ var('passenger_count_domain').max }})
        {% else %}
        (passenger_count IS NOT NULL AND passenger_count > 0)
        {% endif %}                                                         AS pass_dq_008,
        -- Evaluated against the ORIGINAL value, not the uppercased one. Normalising before
        -- validating would silently convert 'y' into a valid 'Y' and erase the evidence that
        -- the source system emits inconsistent casing (profiling §9.2).
        (store_and_fwd_flag_original IN ('Y', 'N'))                          AS pass_dq_011
    FROM {{ ref('silver_typed') }}
)

SELECT
    *,
    -- DQ-008 and DQ-011 are flags: they never remove a row (profiling §2, BDD-03).
    NOT pass_dq_008 AS is_passenger_count_anomaly,
    NOT pass_dq_011 AS is_store_fwd_flag_anomaly,

    -- Coordinate anomaly class, contract taxonomy. GEO-005 is a classification, not a rejection.
    CASE
        WHEN pickup_latitude IS NULL OR pickup_longitude IS NULL
          OR dropoff_latitude IS NULL OR dropoff_longitude IS NULL           THEN 'GEO-001'
        WHEN ABS(pickup_latitude) > 90 OR ABS(dropoff_latitude) > 90         THEN 'GEO-002'
        WHEN ABS(pickup_longitude) > 180 OR ABS(dropoff_longitude) > 180     THEN 'GEO-003'
        WHEN NOT pass_dq_009 OR NOT pass_dq_010                              THEN 'GEO-004'
        WHEN pickup_latitude = dropoff_latitude
         AND pickup_longitude = dropoff_longitude                            THEN 'GEO-005'
        ELSE NULL
    END                                                                      AS coordinate_anomaly,

    -- First failing hard rule, in id order — this becomes the quarantine reason.
    CASE
        WHEN NOT pass_dq_001 THEN 'DQ-001|MISSING_PRIMARY_KEY'
        WHEN NOT pass_dq_002 THEN 'DQ-002|DUPLICATE_PRIMARY_KEY'
        WHEN NOT pass_dq_003 THEN 'DQ-003|VENDOR_OUT_OF_DOMAIN'
        WHEN NOT pass_dq_004 THEN 'DQ-004|MISSING_PICKUP_TIMESTAMP'
        WHEN NOT pass_dq_005 THEN 'DQ-005|MISSING_DROPOFF_TIMESTAMP'
        WHEN NOT pass_dq_006 THEN 'DQ-006|NEGATIVE_TIME_INTERVAL'
        WHEN NOT pass_dq_007 THEN 'DQ-007|NON_POSITIVE_DURATION'
        WHEN NOT pass_dq_009 THEN 'DQ-009|PICKUP_COORDINATE_IMPLAUSIBLE'
        WHEN NOT pass_dq_010 THEN 'DQ-010|DROPOFF_COORDINATE_IMPLAUSIBLE'
        WHEN NOT pass_dq_012 THEN 'DQ-012|NEGATIVE_DERIVED_DISTANCE'
        WHEN NOT pass_dq_013 THEN 'DQ-013|NEGATIVE_DERIVED_SPEED'
        ELSE NULL
    END                                                                      AS quarantine_reason,

    (pass_dq_001 AND pass_dq_002 AND pass_dq_003 AND pass_dq_004 AND pass_dq_005
     AND pass_dq_006 AND pass_dq_007 AND pass_dq_009 AND pass_dq_010
     AND pass_dq_012 AND pass_dq_013)                                        AS is_valid_trip
FROM e
