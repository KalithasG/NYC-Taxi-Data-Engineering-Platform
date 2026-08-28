/*
  Every rejected row, with its rule id and reason (DQ-015).

  All original columns are kept verbatim. That is what makes a rejection reversible: if a rule
  turns out to be wrong, these rows can be replayed. Keeping only the reason would not allow that.

  The reconciliation total = valid + quarantined is asserted in gold.data_quality and by
  tests/test_pipeline_e2e.py. If it ever fails, something is dropping data silently.
*/
SELECT
    id, vendor_id,
    pickup_datetime, dropoff_datetime, passenger_count,
    pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude,
    store_and_fwd_flag_original AS store_and_fwd_flag,
    trip_duration,
    estimated_distance_km, estimated_speed_kmh,
    SPLIT(quarantine_reason, '\\|')[0] AS rule_id,
    SPLIT(quarantine_reason, '\\|')[1] AS quarantine_reason,
    coordinate_anomaly,
    source_file, source_hash, ingested_at
FROM {{ ref('silver_dq_evaluated') }}
WHERE NOT is_valid_trip
