{#
  Silver derivations, defined once here and referenced everywhere. A derivation repeated
  inline in three models is a derivation that will eventually disagree with itself.
#}

{% macro haversine_km(lat1, lon1, lat2, lon2) -%}
{#- Great-circle distance, Earth radius 6371 km (contract §16 / profiling spec §16).
    GEODESIC, not road distance — every column built from this carries the estimated_ prefix. -#}
    ROUND(
        2 * 6371.0 * ASIN(SQRT(
            POW(SIN(RADIANS({{ lat2 }} - {{ lat1 }}) / 2), 2)
            + COS(RADIANS({{ lat1 }})) * COS(RADIANS({{ lat2 }}))
              * POW(SIN(RADIANS({{ lon2 }} - {{ lon1 }}) / 2), 2)
        )), 6)
{%- endmacro %}

{% macro time_of_day(ts) -%}
{#- Analytical categories, not business facts (profiling spec §12). Changing them is a
    presentation change, not a KPI definition change. -#}
    CASE
        WHEN HOUR({{ ts }}) BETWEEN 5  AND 11 THEN 'Morning'
        WHEN HOUR({{ ts }}) BETWEEN 12 AND 16 THEN 'Afternoon'
        WHEN HOUR({{ ts }}) BETWEEN 17 AND 20 THEN 'Evening'
        ELSE 'Night'
    END
{%- endmacro %}

{% macro is_weekend(ts) -%}
    CASE WHEN DAYOFWEEK({{ ts }}) IN (1, 7) THEN TRUE ELSE FALSE END
{%- endmacro %}
