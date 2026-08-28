-- DQ-007: every trip in the trusted population has a positive duration.
-- Returns offending rows; dbt fails the test if any come back.
SELECT id, trip_duration
FROM {{ ref('silver_trips') }}
WHERE trip_duration IS NULL OR trip_duration <= 0
