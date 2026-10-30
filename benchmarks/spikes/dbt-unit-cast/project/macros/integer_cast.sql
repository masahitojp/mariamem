{# Experiment only: signed integer fixtures, not a general adapter fix. #}
{% macro mariadb__safe_cast(field, type) %}
  {% set integer_base = type.lower().split('(')[0].strip() %}
  {% if integer_base in ['int', 'integer', 'tinyint', 'smallint', 'mediumint', 'bigint'] %}
    cast({{ field }} as signed)
  {% else %}
    cast({{ field }} as {{ type }})
  {% endif %}
{% endmacro %}
