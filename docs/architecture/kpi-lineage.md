# KPI Lineage — NYC Taxi Data Engineering Platform

**Generated from `configs/kpi_config.yml`** by
`.claude/skills/kpi-lineage-doc/scripts/check_lineage.py --scaffold`.

KPI contract §17 requires every Gold KPI to have a traceable chain:

```text
Source Column -> Silver Derived Column -> Transformation -> Gold Metric -> Consumer
```

The point is an answerable question. When someone asks "where does this number come from?", the
answer should be this document, not an afternoon of reading SQL.

## Status

The **source → Silver → transformation → Gold** portion is derived from the KPI contract and is
authoritative. Two caveats a reader should carry:

- **Consumer is provisional.** No dashboard exists yet, so those entries record intent rather
  than an observed dependency. Revisit once the AI/BI dashboard is built.
- **Silver columns are inferred** from each KPI's formula, grain, filter and dimensions. They
  match the derived-field list in spec §5, but the transformations that produce them are not
  written yet — so this is the specification for the lineage, not a record of an implemented one.

Re-run the scaffold whenever `configs/kpi_config.yml` changes, and check coverage with:

```bash
python3 .claude/skills/kpi-lineage-doc/scripts/check_lineage.py --strict
```

---


### KPI-001 — Total Trips

```text
pickup_latitude
pickup_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
pickup_area
        |
        v   COUNT(DISTINCT id)
KPI-001 Total Trips   ->   gold.trip_performance
        |
        v
Executive dashboard — trip performance tiles
```

- **Source:** pickup_latitude, pickup_longitude
- **Silver:** pickup_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** COUNT(DISTINCT id)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — trip performance tiles

### KPI-002 — Average Trip Duration

```text
pickup_latitude
pickup_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
pickup_area
        |
        v   AVG(trip_duration)
KPI-002 Average Trip Duration   ->   gold.trip_performance
        |
        v
Executive dashboard — trip performance tiles
```

- **Source:** pickup_latitude, pickup_longitude
- **Silver:** pickup_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** AVG(trip_duration)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — trip performance tiles

### KPI-003 — Median Trip Duration

```text
trip_duration
        |
        v   passthrough, validated by DQ-007
trip_duration
        |
        v   PERCENTILE_CONT(0.50, trip_duration)
KPI-003 Median Trip Duration   ->   gold.trip_performance
        |
        v
Executive dashboard — trip performance tiles
```

- **Source:** trip_duration
- **Silver:** trip_duration — passthrough, validated by DQ-007
- **Transformation:** PERCENTILE_CONT(0.50, trip_duration)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — trip performance tiles

### KPI-004 — P90 Trip Duration

```text
trip_duration
        |
        v   passthrough, validated by DQ-007
trip_duration
        |
        v   PERCENTILE_CONT(0.90, trip_duration)
KPI-004 P90 Trip Duration   ->   gold.trip_performance
        |
        v
Executive dashboard — trip performance tiles
```

- **Source:** trip_duration
- **Silver:** trip_duration — passthrough, validated by DQ-007
- **Transformation:** PERCENTILE_CONT(0.90, trip_duration)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — trip performance tiles

### KPI-005 — Average Estimated Distance

```text
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
        |
        v   Haversine transformation (Earth radius 6371 km)
estimated_distance_km
        |
        v   AVG(estimated_distance_km)
KPI-005 Average Estimated Distance   ->   gold.trip_performance
        |
        v
Operations dashboard
```

- **Source:** pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude
- **Silver:** estimated_distance_km — Haversine transformation (Earth radius 6371 km)
- **Transformation:** AVG(estimated_distance_km)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true AND coordinates_valid = true`
- **Consumer:** Operations dashboard
- **Caveat:** Straight-line Haversine distance, NOT road-network distance. Must never be labelled as actual route distance (contract §4, BDD-07).

### KPI-006 — Average Estimated Speed

```text
pickup_latitude
pickup_longitude
dropoff_latitude
dropoff_longitude
trip_duration
        |
        v   estimated_distance_km / (trip_duration / 3600)
estimated_speed_kmh
        |
        v   AVG(estimated_speed_kmh)
KPI-006 Average Estimated Speed   ->   gold.trip_performance
        |
        v
Operations dashboard
```

- **Source:** pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude, trip_duration
- **Silver:** estimated_speed_kmh — estimated_distance_km / (trip_duration / 3600)
- **Transformation:** AVG(estimated_speed_kmh)
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true AND trip_duration > 0 AND coordinates_valid = true`
- **Consumer:** Operations dashboard
- **Caveat:** Derived from geodesic distance. NOT an actual road-speed measurement (contract §6, BDD-07).

### KPI-007 — Trips Per Day

```text
pickup_latitude
pickup_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
pickup_area
        |
        v   COUNT(DISTINCT id) GROUP BY pickup_date
KPI-007 Trips Per Day   ->   gold.demand_metrics
        |
        v
Executive dashboard — demand trend
```

- **Source:** pickup_latitude, pickup_longitude
- **Silver:** pickup_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** COUNT(DISTINCT id) GROUP BY pickup_date
- **Gold:** gold.demand_metrics · grain pickup_date · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — demand trend

### KPI-008 — Trips Per Hour

```text
pickup_datetime
        |
        v   DATE(pickup_datetime)
pickup_date
        |
        v   COUNT(DISTINCT id) GROUP BY pickup_hour
KPI-008 Trips Per Hour   ->   gold.demand_metrics
        |
        v
Executive dashboard — demand trend
```

- **Source:** pickup_datetime
- **Silver:** pickup_date — DATE(pickup_datetime)
- **Transformation:** COUNT(DISTINCT id) GROUP BY pickup_hour
- **Gold:** gold.demand_metrics · grain pickup_date + pickup_hour · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — demand trend

### KPI-009 — Peak Demand Hour

```text
pickup_datetime
        |
        v   HOUR(pickup_datetime)
pickup_hour
        |
        v   ARGMAX(trip_count BY pickup_hour)
KPI-009 Peak Demand Hour   ->   gold.demand_metrics
        |
        v
Executive dashboard — demand trend
```

- **Source:** pickup_datetime
- **Silver:** pickup_hour — HOUR(pickup_datetime)
- **Transformation:** ARGMAX(trip_count BY pickup_hour)
- **Gold:** gold.demand_metrics · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — demand trend

### KPI-010 — Top Pickup Area

```text
pickup_latitude
pickup_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
pickup_area
        |
        v   COUNT(DISTINCT id) GROUP BY pickup_area ORDER BY trip_count DESC LIMIT 1
KPI-010 Top Pickup Area   ->   gold.geographic_metrics
        |
        v
Executive dashboard — top areas / top routes
```

- **Source:** pickup_latitude, pickup_longitude
- **Silver:** pickup_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** COUNT(DISTINCT id) GROUP BY pickup_area ORDER BY trip_count DESC LIMIT 1
- **Gold:** gold.geographic_metrics · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — top areas / top routes

### KPI-011 — Top Drop-off Area

```text
dropoff_latitude
dropoff_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
dropoff_area
        |
        v   COUNT(DISTINCT id) GROUP BY dropoff_area ORDER BY trip_count DESC LIMIT 1
KPI-011 Top Drop-off Area   ->   gold.geographic_metrics
        |
        v
Executive dashboard — top areas / top routes
```

- **Source:** dropoff_latitude, dropoff_longitude
- **Silver:** dropoff_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** COUNT(DISTINCT id) GROUP BY dropoff_area ORDER BY trip_count DESC LIMIT 1
- **Gold:** gold.geographic_metrics · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — top areas / top routes

### KPI-012 — Top Route

```text
pickup_latitude
pickup_longitude
        |
        v   coordinate bucketing (zone polygons deferred — contract §8)
pickup_area
        |
        v   COUNT(DISTINCT id) GROUP BY pickup_area, dropoff_area ORDER BY trip_count DESC LIMIT 1
KPI-012 Top Route   ->   gold.geographic_metrics
        |
        v
Executive dashboard — top areas / top routes
```

- **Source:** pickup_latitude, pickup_longitude
- **Silver:** pickup_area — coordinate bucketing (zone polygons deferred — contract §8)
- **Transformation:** COUNT(DISTINCT id) GROUP BY pickup_area, dropoff_area ORDER BY trip_count DESC LIMIT 1
- **Gold:** gold.geographic_metrics · grain period · filter `is_valid_trip = true`
- **Consumer:** Executive dashboard — top areas / top routes

### KPI-013 — Vendor Trip Share

```text
id
vendor_id
pickup_datetime
dropoff_datetime
passenger_count
coordinates
trip_duration
        |
        v   DQ-001..DQ-013 evaluated per row
is_valid_trip
        |
        v   vendor_trips / total_trips * 100
KPI-013 Vendor Trip Share   ->   gold.vendor_performance
        |
        v
Vendor performance report
```

- **Source:** id, vendor_id, pickup_datetime, dropoff_datetime, passenger_count, coordinates, trip_duration
- **Silver:** is_valid_trip — DQ-001..DQ-013 evaluated per row
- **Transformation:** vendor_trips / total_trips * 100
- **Gold:** gold.vendor_performance · grain vendor + period · filter `is_valid_trip = true`
- **Consumer:** Vendor performance report

### KPI-014 — Vendor Average Duration

```text
vendor_id
        |
        v   passthrough, validated by DQ-003
vendor_id
        |
        v   AVG(trip_duration) GROUP BY vendor_id
KPI-014 Vendor Average Duration   ->   gold.vendor_performance
        |
        v
Vendor performance report
```

- **Source:** vendor_id
- **Silver:** vendor_id — passthrough, validated by DQ-003
- **Transformation:** AVG(trip_duration) GROUP BY vendor_id
- **Gold:** gold.vendor_performance · grain vendor + period · filter `is_valid_trip = true`
- **Consumer:** Vendor performance report

### KPI-015 — Vendor P90 Duration

```text
vendor_id
        |
        v   passthrough, validated by DQ-003
vendor_id
        |
        v   PERCENTILE_CONT(0.90, trip_duration) GROUP BY vendor_id
KPI-015 Vendor P90 Duration   ->   gold.vendor_performance
        |
        v
Vendor performance report
```

- **Source:** vendor_id
- **Silver:** vendor_id — passthrough, validated by DQ-003
- **Transformation:** PERCENTILE_CONT(0.90, trip_duration) GROUP BY vendor_id
- **Gold:** gold.vendor_performance · grain vendor + period · filter `is_valid_trip = true`
- **Consumer:** Vendor performance report
- **Caveat:** Lower P90 suggests better long-tail performance BUT trip mixes differ between vendors. Do not infer operational superiority from this metric alone (contract §9, profiling §23D).

### KPI-016 — Long Trip Rate

```text
id
vendor_id
pickup_datetime
dropoff_datetime
passenger_count
coordinates
trip_duration
        |
        v   DQ-001..DQ-013 evaluated per row
is_valid_trip
        |
        v   long_trips / valid_trips * 100
KPI-016 Long Trip Rate   ->   gold.trip_performance
        |
        v
Operations dashboard — anomaly rates
```

- **Source:** id, vendor_id, pickup_datetime, dropoff_datetime, passenger_count, coordinates, trip_duration
- **Silver:** is_valid_trip — DQ-001..DQ-013 evaluated per row
- **Transformation:** long_trips / valid_trips * 100
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true`
- **Consumer:** Operations dashboard — anomaly rates
- **Depends on threshold:** `long_trip_seconds` (TBD_PENDING_PROFILING)

### KPI-017 — Low-Speed Trip Rate

```text
id
vendor_id
pickup_datetime
dropoff_datetime
passenger_count
coordinates
trip_duration
        |
        v   DQ-001..DQ-013 evaluated per row
is_valid_trip
        |
        v   low_speed_trips / valid_trips * 100
KPI-017 Low-Speed Trip Rate   ->   gold.trip_performance
        |
        v
Operations dashboard — anomaly rates
```

- **Source:** id, vendor_id, pickup_datetime, dropoff_datetime, passenger_count, coordinates, trip_duration
- **Silver:** is_valid_trip — DQ-001..DQ-013 evaluated per row
- **Transformation:** low_speed_trips / valid_trips * 100
- **Gold:** gold.trip_performance · grain period · filter `is_valid_trip = true AND coordinates_valid = true`
- **Consumer:** Operations dashboard — anomaly rates
- **Caveat:** MUST NOT be presented as confirmed congestion. Candidate causes include traffic, route vs straight-line divergence, waiting time inside duration, coordinate quality, or a genuinely unusual trip (contract §10, profiling §22).
- **Depends on threshold:** `low_speed_kmh` (TBD_PENDING_PROFILING)

### KPI-018 — Data Quality Score

```text
all source columns
        |
        v   valid_records / total_records — evaluated over ALL source records
silver_trips + silver_trips_quarantine
        |
        v   valid_records / total_records * 100
KPI-018 Data Quality Score   ->   gold.data_quality
        |
        v
Data quality dashboard; pipeline run report
```

- **Source:** all source columns
- **Silver:** silver_trips + silver_trips_quarantine — valid_records / total_records — evaluated over ALL source records
- **Transformation:** valid_records / total_records * 100
- **Gold:** gold.data_quality · grain batch · filter `none — evaluated over ALL source records`
- **Consumer:** Data quality dashboard; pipeline run report

### KPI-019 — Invalid Record Rate

```text
all source columns
        |
        v   invalid_records / total_records — the complement of KPI-018
silver_trips_quarantine
        |
        v   invalid_records / total_records * 100
KPI-019 Invalid Record Rate   ->   gold.data_quality
        |
        v
Data quality dashboard; pipeline run report
```

- **Source:** all source columns
- **Silver:** silver_trips_quarantine — invalid_records / total_records — the complement of KPI-018
- **Transformation:** invalid_records / total_records * 100
- **Gold:** gold.data_quality · grain batch · filter `none`
- **Consumer:** Data quality dashboard; pipeline run report

### KPI-020 — Duplicate Rate

```text
id
        |
        v   duplicate_records / total_records — read from the PRE-deduplication count
duplicate audit table
        |
        v   duplicate_records / total_records * 100
KPI-020 Duplicate Rate   ->   gold.data_quality
        |
        v
Data quality dashboard; pipeline run report
```

- **Source:** id
- **Silver:** duplicate audit table — duplicate_records / total_records — read from the PRE-deduplication count
- **Transformation:** duplicate_records / total_records * 100
- **Gold:** gold.data_quality · grain batch · filter `none`
- **Consumer:** Data quality dashboard; pipeline run report

