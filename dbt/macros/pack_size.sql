{% macro pack_size(p) -%}
    nullif(
        concat_ws(' ',
            trim_scale({{ p }}.size_value),
            case lower({{ p }}.size_unit)
                when 'gr' then 'g'
                when 'gram' then 'g'
                when 'l' then 'L'
                else nullif({{ p }}.size_unit, '')
            end
        ) || case when {{ p }}.pack_qty > 1 then ' x ' || {{ p }}.pack_qty else '' end,
        ''
    )
{%- endmacro %}
