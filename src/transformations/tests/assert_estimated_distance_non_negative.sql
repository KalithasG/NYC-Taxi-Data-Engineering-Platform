-- DQ-012 / DQ-013: a negative geodesic distance or speed indicates a defect in the
-- transformation, not bad source data. Treat a hit here as a bug report against the pipeline.
SELECT id, estimated_distance_km, estimated_speed_kmh
FROM {{ ref('silver_trips') }}
WHERE estimated_distance_km < 0 OR estimated_speed_kmh < 0
