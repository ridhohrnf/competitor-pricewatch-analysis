{% test positive_value(model, column_name) %}
select {{ column_name }} as failing_value
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} <= 0
{% endtest %}
