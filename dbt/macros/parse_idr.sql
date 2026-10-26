{% macro parse_idr(column) -%}
    case
        when {{ column }} ~ '^\s*Rp\s?[0-9]{1,3}(\.[0-9]{3})*\s*$'
            then regexp_replace({{ column }}, '[^0-9]', '', 'g')::numeric
    end
{%- endmacro %}
