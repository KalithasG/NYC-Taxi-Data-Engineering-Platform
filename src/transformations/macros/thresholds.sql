{#
  Threshold governance at compile time.

  Six thresholds are deliberately unset (KPI contract §18). A model that silently substituted
  a default would turn an unreviewed policy decision into a number nobody can trace — which is
  the exact failure BDD-05 exists to prevent. These macros make the state explicit instead.
#}

{% macro threshold_is_approved(name) -%}
{#- True only when the var holds a real value rather than the pending sentinel. -#}
    {%- set v = var(name, 'TBD_PENDING_PROFILING') -%}
    {{- (v is not none and v | string != 'TBD_PENDING_PROFILING' and v | string != 'None') -}}
{%- endmacro %}

{% macro approved_threshold(name) -%}
{#- Emit the value, or stop the build with an explicit, actionable error (BDD-05). -#}
    {%- set v = var(name, 'TBD_PENDING_PROFILING') -%}
    {%- if v is none or v | string == 'TBD_PENDING_PROFILING' or v | string == 'None' -%}
        {{- exceptions.raise_compiler_error(
            "Threshold '" ~ name ~ "' is TBD_PENDING_PROFILING. It cannot be defaulted or "
            ~ "guessed: run the profiling spec, record the decision with evidence in "
            ~ "docs/profiling/threshold-decisions.md, and have a human approve it. "
            ~ "See the threshold-decision skill.") -}}
    {%- endif -%}
    {{- v -}}
{%- endmacro %}

{% macro withheld_note(kpi_id, threshold_name) -%}
{#- Records, in the model itself, why a KPI column is absent. Not silence: a reader of the
    Gold table can see the KPI was withheld and what would release it. -#}
    CAST(NULL AS DOUBLE) AS {{ kpi_id | lower | replace('-', '_') }}_withheld_pending_{{ threshold_name }}
{%- endmacro %}
