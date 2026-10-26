{#- Custom generic test: values stay inside [min_value, max_value] (e.g. discount_pct 0-100). -#}
{% test value_between(model, column_name, min_value, max_value) %}
select {{ column_name }} as failing_value
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}
