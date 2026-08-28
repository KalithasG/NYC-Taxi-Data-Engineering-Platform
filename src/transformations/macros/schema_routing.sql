{#
  Route models to a Unity Catalog schema per medallion layer.

  dbt's built-in generate_schema_name PREFIXES a custom schema with the target schema, so
  `+schema: gold` would produce `nyc_taxi_dev_gold` — a fifth schema nobody declared, and not
  the `gold` that resources/catalog.yml creates or that resources/permissions.yml grants on.
  Per-layer grants only work if the physical schema name matches the granted one exactly.

  So: a custom schema is used verbatim; models without one fall back to the profile's schema.
  Contract v1.2 (docs/business/kpi-changelog.md) relocated the Gold marts on this basis.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
